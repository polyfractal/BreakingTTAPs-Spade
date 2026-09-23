#!/usr/bin/env python3
"""
Test Vector Extraction Tool for BreakingTTAPs

This tool parses cocotb test files and extracts test vectors as JSON
for verifying the Rust behavioral simulator.

Usage:
    python extract_vectors.py
"""

import json
import re
import ast
from dataclasses import dataclass, field
from typing import Any, Optional, List, Dict
from pathlib import Path


@dataclass
class CycleRecord:
    """Record of inputs and expected outputs for a single cycle"""
    cycle: int
    inputs: Dict[str, Any] = field(default_factory=dict)
    expected_outputs: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self):
        return {
            "cycle": self.cycle,
            "inputs": self.inputs,
            "expected": self.expected_outputs
        }


@dataclass
class TestVector:
    """Complete test vector for a single test case"""
    test_name: str
    fu: str
    description: str = ""
    cycles: List[CycleRecord] = field(default_factory=list)

    def to_dict(self):
        return {
            "test_name": self.test_name,
            "fu": self.fu,
            "description": self.description,
            "cycles": [c.to_dict() for c in self.cycles]
        }


def parse_spade_value(value_str: str) -> Any:
    """
    Parse a Spade value string into a Python representation.
    """
    if value_str is None:
        return None

    value_str = str(value_str).strip()

    # Boolean
    if value_str == "true" or value_str == "True":
        return True
    if value_str == "false" or value_str == "False":
        return False

    # None
    if value_str == "None":
        return None

    # Plain integer
    try:
        return int(value_str)
    except ValueError:
        pass

    # Some(value)
    some_match = re.match(r'^Some\((.+)\)$', value_str)
    if some_match:
        inner = some_match.group(1)
        return {"Some": parse_spade_inner(inner)}

    # Fallback: return as string
    return value_str


def parse_spade_inner(inner: str) -> Any:
    """Parse the inner value of Some(...)"""
    inner = inner.strip()

    # Plain integer
    try:
        return int(inner)
    except ValueError:
        pass

    # Tuple like (AluOp::Add, 1) or (CmpOp::Eq, 10)
    tuple_match = re.match(r'^\(([A-Za-z]+)::([A-Za-z]+)(?:\(\))?,\s*(-?\d+)\)$', inner)
    if tuple_match:
        variant = tuple_match.group(2)
        operand = int(tuple_match.group(3))
        return {"op": variant, "operand": operand}

    # Tuple like (register_id, value)
    tuple_match2 = re.match(r'^\((\d+),\s*(\d+)\)$', inner)
    if tuple_match2:
        return {"index": int(tuple_match2.group(1)), "value": int(tuple_match2.group(2))}

    # Fallback
    return inner


def ast_to_value(node) -> Optional[str]:
    """Convert an AST node to a string value"""
    if isinstance(node, ast.Constant):
        if isinstance(node.value, str):
            return node.value
        elif isinstance(node.value, bool):
            return "true" if node.value else "false"
        return str(node.value)
    elif isinstance(node, ast.Name):
        if node.id == 'True':
            return 'true'
        elif node.id == 'False':
            return 'false'
        return node.id
    elif isinstance(node, ast.JoinedStr):
        # f-string - try to reconstruct
        parts = []
        for val in node.values:
            if isinstance(val, ast.Constant):
                parts.append(str(val.value))
            elif isinstance(val, ast.FormattedValue):
                # Try to get the variable value
                if isinstance(val.value, ast.Name):
                    parts.append(f"${{{val.value.id}}}")
                else:
                    parts.append("{...}")
        return "".join(parts)
    return None


def is_falling_edge_await(stmt) -> bool:
    """Check if a statement is 'await FallingEdge(...)'"""
    if not isinstance(stmt, ast.Expr):
        return False
    if not isinstance(stmt.value, ast.Await):
        return False
    await_val = stmt.value.value
    if not isinstance(await_val, ast.Call):
        return False
    func = await_val.func
    if isinstance(func, ast.Name) and func.id == 'FallingEdge':
        return True
    return False


def is_input_assignment(stmt) -> Optional[tuple]:
    """
    Check if statement is 's.i.X = value' and return (name, value) or None
    """
    if not isinstance(stmt, ast.Assign):
        return None
    if len(stmt.targets) != 1:
        return None

    target = stmt.targets[0]

    # Match s.i.X pattern
    if not isinstance(target, ast.Attribute):
        return None
    if not isinstance(target.value, ast.Attribute):
        return None
    if not isinstance(target.value.value, ast.Name):
        return None

    # Check it's s.i.something
    if target.value.attr != 'i':
        return None

    input_name = target.attr
    value = ast_to_value(stmt.value)

    return (input_name, value)


def is_output_assertion(stmt) -> Optional[str]:
    """
    Check if statement is 's.o.assert_eq(...)' and return expected value or None
    """
    if not isinstance(stmt, ast.Expr):
        return None
    if not isinstance(stmt.value, ast.Call):
        return None

    call = stmt.value
    func = call.func

    # Match s.o.assert_eq or s.o.field.assert_eq
    if not isinstance(func, ast.Attribute):
        return None
    if func.attr != 'assert_eq':
        return None

    if call.args:
        return ast_to_value(call.args[0])
    return None


def extract_vector_from_function(func_node: ast.AsyncFunctionDef, fu_name: str) -> Optional[TestVector]:
    """Extract test vector by sequentially processing function body"""
    test_name = func_node.name
    description = ast.get_docstring(func_node) or ""

    cycles = []
    current_cycle = 0
    current_inputs = {}
    pending_outputs = {}

    def commit_cycle(force=False):
        nonlocal current_cycle, current_inputs, pending_outputs
        # Always commit if forced (FallingEdge), or if there's content
        if force or current_inputs or pending_outputs:
            cycles.append(CycleRecord(
                cycle=current_cycle,
                inputs=current_inputs.copy(),
                expected_outputs=pending_outputs.copy()
            ))
            current_cycle += 1
            current_inputs = {}
            pending_outputs = {}

    def process_statements(stmts):
        nonlocal current_inputs, pending_outputs

        for stmt in stmts:
            # Check for input assignment
            input_result = is_input_assignment(stmt)
            if input_result:
                name, value = input_result
                current_inputs[name] = parse_spade_value(value)
                continue

            # Check for FallingEdge await - signals end of input phase
            if is_falling_edge_await(stmt):
                # Commit current cycle (force=True even if no inputs)
                commit_cycle(force=True)
                continue

            # Check for output assertion - goes with the just-committed cycle
            output_result = is_output_assertion(stmt)
            if output_result:
                # This assertion is checking the output after the previous FallingEdge
                # Add to the last cycle
                if cycles:
                    cycles[-1].expected_outputs["result"] = parse_spade_value(output_result)
                continue

            # Handle for loops (common in MUL/DIV tests)
            if isinstance(stmt, ast.For):
                # Try to get loop count
                if isinstance(stmt.iter, ast.Call):
                    if isinstance(stmt.iter.func, ast.Name) and stmt.iter.func.id == 'range':
                        if stmt.iter.args:
                            try:
                                loop_count = ast.literal_eval(stmt.iter.args[0])
                                # Process loop body for each iteration
                                for _ in range(loop_count):
                                    process_statements(stmt.body)
                            except:
                                # Can't determine loop count, process body once
                                process_statements(stmt.body)
                continue

            # Handle while loops
            if isinstance(stmt, ast.While):
                # Process body once (we can't know iteration count)
                process_statements(stmt.body)
                continue

            # Handle if statements
            if isinstance(stmt, ast.If):
                process_statements(stmt.body)
                if stmt.orelse:
                    process_statements(stmt.orelse)
                continue

    # Skip the docstring if present
    body = func_node.body
    if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
        body = body[1:]

    process_statements(body)

    # Commit any remaining cycle
    commit_cycle()

    if not cycles:
        return None

    return TestVector(
        test_name=test_name,
        fu=fu_name,
        description=description,
        cycles=cycles
    )


def extract_vectors_from_test_file(test_file: Path, fu_name: str) -> List[TestVector]:
    """Parse a test file and extract test vectors."""
    vectors = []

    with open(test_file, 'r') as f:
        source = f.read()

    tree = ast.parse(source)

    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.AsyncFunctionDef):
            # Check for @cocotb.test() decorator
            is_test = any(
                (isinstance(d, ast.Call) and
                 isinstance(d.func, ast.Attribute) and
                 d.func.attr == 'test')
                or (isinstance(d, ast.Attribute) and d.attr == 'test')
                for d in node.decorator_list
            )

            if is_test:
                vector = extract_vector_from_function(node, fu_name)
                if vector and vector.cycles:
                    vectors.append(vector)

    return vectors


def export_vectors_to_json(vectors: List[TestVector], output_path: Path):
    """Export test vectors to a JSON file"""
    data = {
        "vectors": [v.to_dict() for v in vectors]
    }

    with open(output_path, 'w') as f:
        json.dump(data, f, indent=2)

    print(f"  Exported {len(vectors)} test vectors to {output_path}")


def main():
    """Main entry point"""
    test_dir = Path("/home/polyfractal/Documents/asic/BreakingTTAPs-Spade/test")
    output_dir = Path("/home/polyfractal/Documents/asic/ttap/breakingttaps-sim/test_vectors")

    output_dir.mkdir(parents=True, exist_ok=True)

    # Map test files to FU names
    test_files = {
        "alu.py": "alu",
        "mul_shiftadd.py": "mul",
        "div_shiftsub.py": "div",
        "cmp.py": "cmp",
        "cmpz.py": "cmpz",
        "mac.py": "mac",
        "bit.py": "bit",
        "bt.py": "bt",
        "lalu.py": "lalu",
        "lsu.py": "lsu",
        "sel.py": "sel",
        "stack_lsu.py": "stack",
        "regfile8.py": "regfile",
        "pc.py": "pc",
        # Additional FUs
        "fifo.py": "fifo",
        "modadd.py": "modadd",
        "tanh.py": "tanh",
        "xorshift.py": "xorshift",
        "spi.py": "spi",
        "uart.py": "uart",
        "parallel_rx.py": "parallel_rx",
    }

    all_vectors = {}

    for test_file, fu_name in test_files.items():
        test_path = test_dir / test_file
        if test_path.exists():
            print(f"Extracting from {test_file}...")
            vectors = extract_vectors_from_test_file(test_path, fu_name)
            if vectors:
                all_vectors[fu_name] = vectors
                output_path = output_dir / f"{fu_name}.json"
                export_vectors_to_json(vectors, output_path)
        else:
            print(f"Warning: {test_file} not found")

    # Summary
    print(f"\nExtraction complete:")
    total = 0
    total_cycles = 0
    for fu, vectors in all_vectors.items():
        cycles = sum(len(v.cycles) for v in vectors)
        print(f"  {fu}: {len(vectors)} tests, {cycles} cycles")
        total += len(vectors)
        total_cycles += cycles
    print(f"  Total: {total} test vectors, {total_cycles} cycles")


if __name__ == "__main__":
    main()
