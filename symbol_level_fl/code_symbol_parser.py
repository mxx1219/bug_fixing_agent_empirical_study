import ast
import os
import json

class CodeEntityVisitor(ast.NodeVisitor):
    """AST visitor for extracting code entities (functions, classes, imports, etc.) from Python source code."""
    def __init__(self):
        self.functions = []
        self.methods = []
        self.classes = []
        self.import_blocks = []
        self.current_import_block = []
        self.top_level_statements = []
        self.source_code = None  # Store original source code for text extraction
        self.current_class = None  # Track current class context for method detection

    def visit_FunctionDef(self, node):
        """Process function definitions (sync functions)"""
        self._process_function(node, 'function')
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node):
        """Process async function definitions"""
        self._process_function(node, 'async function')
        self.generic_visit(node)

    def _process_function(self, node, kind):
        """Common processing logic for both sync and async functions"""
        # Determine start line including decorators if present
        start_line = min(dec.lineno for dec in node.decorator_list) if node.decorator_list else node.lineno
        entity = {
            'source': self._get_source_segment(start_line, node.end_lineno),
            'start_line': start_line,
            'end_line': node.end_lineno,
            'type': kind
        }
        if self.current_class is None:
            self.functions.append(entity)
        else:
            entity['class'] = self.current_class
            self.methods.append(entity)

    def visit_ClassDef(self, node):
        """Process class definitions and track class context"""
        previous_class = self.current_class
        self.current_class = node.name  # Update current class context

        # Handle class definition with decorators
        start_line = min(dec.lineno for dec in node.decorator_list) if node.decorator_list else node.lineno
        class_def = {
            'name': node.name,
            'source': self._get_source_segment(start_line, node.end_lineno),
            'start_line': start_line,
            'end_line': node.end_lineno
        }
        self.classes.append(class_def)

        self.generic_visit(node)  # Continue visiting child nodes
        self.current_class = previous_class  # Restore previous class context

    def visit_Import(self, node):
        """Handle import statements"""
        self._process_import(node)

    def visit_ImportFrom(self, node):
        """Handle from-import statements"""
        self._process_import(node)

    def _process_import(self, node):
        """Group consecutive import statements into blocks"""
        if not self.current_import_block:
            self.current_import_block.append(node)
        else:
            last_node = self.current_import_block[-1]
            # Check if imports are consecutive or separated by blank lines only
            if node.lineno == last_node.end_lineno + 1 or self._is_blank_line_between(last_node.end_lineno, node.lineno):
                self.current_import_block.append(node)
            else:
                self._finalize_import_block()
                self.current_import_block.append(node)

    def _is_blank_line_between(self, start_line, end_line):
        """Check if lines between given range are empty"""
        lines = self.source_code.splitlines()
        for i in range(start_line, end_line - 1):
            if lines[i].strip() != '':
                return False
        return True

    def _finalize_import_block(self):
        """Finalize current import block and add to collection"""
        if self.current_import_block:
            start_line = self.current_import_block[0].lineno
            end_line = self.current_import_block[-1].end_lineno
            source = self._get_source_segment(start_line, end_line)
            self.import_blocks.append({
                'source': source,
                'start_line': start_line,
                'end_line': end_line
            })
            self.current_import_block = []

    def visit_Module(self, node):
        """Process module-level statements (top-level code)"""
        # Collect non-entity top-level statements
        self.top_level_statements = [
            {
                'source': self._get_source_segment(stmt.lineno, stmt.end_lineno),
                'start_line': stmt.lineno,
                'end_line': stmt.end_lineno
            }
            for stmt in node.body if not isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Import, ast.ImportFrom))
        ]
        self.generic_visit(node)
        self._finalize_import_block()  # Finalize any remaining imports

    def _get_source_segment(self, start_line, end_line):
        """Extract source code segment from given line range"""
        lines = self.source_code.splitlines()
        return '\n'.join(lines[start_line - 1: end_line])

def _find_end_lineno(node):
    """Recursively find the last line number of an AST node"""
    last_line = node.lineno
    for child in ast.iter_child_nodes(node):
        if hasattr(child, 'lineno'):
            last_line = max(last_line, _find_end_lineno(child))
    return last_line

def get_code_entities(file_path):
    """Main function to extract code entities from a file"""
    with open(file_path, 'r', encoding='utf-8') as file:
        source_code = file.read()

    # Parse AST and add end_lineno attribute to nodes
    tree = ast.parse(source_code, filename=file_path)
    for node in ast.walk(tree):
        if hasattr(node, 'lineno') and not hasattr(node, 'end_lineno'):
            node.end_lineno = _find_end_lineno(node)

    visitor = CodeEntityVisitor()
    visitor.source_code = source_code
    visitor.visit(tree)

    return visitor.functions, visitor.methods, visitor.classes, visitor.import_blocks, visitor.top_level_statements

def check_if_valid(file_path, line_list):
    """Verify that all non-comment lines are covered"""
    with open(file_path, "r") as file:
        content = file.readlines()
    no_cover_line_list = [line for line in range(1, len(content)+1) if line not in line_list]
    for line_num in no_cover_line_list:
        line_content = content[line_num-1].strip()
        if line_content and not line_content.startswith("#"):
            raise Exception(f"no-cover line error: {line_num}: {line_content}")

def group_numbers(numbers):
    """Convert list of numbers to range strings (e.g., 1,2,3,5 -> '1-3,5')"""
    # Sort input numbers first
    numbers.sort()
    # Initialize result list and temporary list
    result = []
    temp = []
    
    for num in numbers:
        if not temp or num == temp[-1] + 1:
            temp.append(num)
        else:
            # Convert temp list to string and add to result
            if len(temp) == 1:
                result.append(str(temp[0]))
            else:
                result.append(f"{temp[0]}-{temp[-1]}")
            temp = [num]
    
    # Handle remaining elements in temp list
    if temp:
        if len(temp) == 1:
            result.append(str(temp[0]))
        else:
            result.append(f"{temp[0]}-{temp[-1]}")
            
    return ",".join(result)

def generate_formated_entities(entities):
    """Process and format code entities with proper line ranges"""
    top_level_stmt_line_ranges = []
    other_line_ranges = []
    other_line_range_list = []
    for entity_name in entities:
        factors = entities[entity_name]
        if entity_name == "top_level_statements":
            # Collect top-level statement ranges
            for factor in factors:
                top_level_stmt_line_ranges.append([factor["start_line"], factor["end_line"]])
        else:
            # Collect lines from other entities
            for factor in factors:
                other_line_ranges += [i for i in range(factor["start_line"], factor["end_line"]+1)]
                other_line_range_list.append([i for i in range(factor["start_line"], factor["end_line"]+1)])
    
    # Process top-level statements ranges
    top_level_stmt_line_ranges = sorted(top_level_stmt_line_ranges)
    other_line_ranges = sorted(list(set(other_line_ranges)))
    combined_top_level_line_ranges = []
    
    # Combine adjacent top-level statement ranges
    for line_range in top_level_stmt_line_ranges:
        if not combined_top_level_line_ranges:
            combined_top_level_line_ranges.append(line_range)
        else:
            flag = True
            # Check if there are other entities between ranges
            for i in range(combined_top_level_line_ranges[-1][1]+1, line_range[0]):
                if i in other_line_ranges:
                    flag = False
                    break
            if flag:
                combined_top_level_line_ranges[-1][1] = line_range[1]
            else:
                combined_top_level_line_ranges.append(line_range)
    
    # Update entities with combined ranges
    entities["top_level_statements"] = [{"start_line": line_range[0], "end_line": line_range[1]} for line_range in combined_top_level_line_ranges]
    
    # Get new top-level statement line ranges
    top_level_stmt_line_range_list = []
    for factor in entities["top_level_statements"]:
        top_level_stmt_line_range_list.append([i for i in range(factor["start_line"], factor["end_line"]+1)])
    
    # Filter out imports that are inside other entities
    imports = entities["imports"]
    imports_except_inners = []
    for factor in imports:
        flag = False
        for some_range in other_line_range_list + top_level_stmt_line_range_list:
            # Check if import is contained within other ranges
            if (min(some_range) <= factor["start_line"] and max(some_range) > factor["end_line"]) or (min(some_range) < factor["start_line"] and max(some_range) >= factor["end_line"]):
                flag = True
                break
        if flag:
            other_line_range_list.remove([i for i in range(factor["start_line"], factor["end_line"]+1)])
        else:
            imports_except_inners.append(factor)
    entities["imports"] = imports_except_inners
    
    # Generate final formatted entities
    formated_entities = []
    for entity_name in entities:
        for factor in entities[entity_name]:
            current_line_range = [i for i in range(factor["start_line"], factor["end_line"]+1)]
            # Exclude lines covered by other entities
            for some_range in other_line_range_list:
                if (min(some_range) >= min(current_line_range) and max(some_range) < max(current_line_range)) or (min(some_range) > min(current_line_range) and max(some_range) <= max(current_line_range)):
                    current_line_range = list(set(current_line_range) - set(some_range))
            formated_entities.append({"type": entity_name, "line_range": group_numbers(current_line_range)})
    return formated_entities

def extract_and_print_entities(file_path):
    """Main workflow: extract entities, validate coverage, and format results"""
    functions, methods, classes, imports, top_level_statements = get_code_entities(file_path)
    entities = {
        "functions": functions,
        "methods": methods,
        "classes": classes,
        "imports": imports,
        "top_level_statements": top_level_statements
    }
    
    # Collect all covered lines for validation
    lines = []
    for entity_name in entities:
        for factor in entities[entity_name]:
            lines += [i for i in range(factor["start_line"], factor["end_line"]+1)]
    
    # Validate code coverage
    check_if_valid(file_path, lines)

    solved_entities = generate_formated_entities(entities)
    return solved_entities

if __name__ == "__main__":
    """Main entry point for processing code entities in bulk"""
    data_dir = "./data/techniques/"
    # count = 0  # Counter variable (currently unused)
    for case_id in os.listdir(data_dir):
        buggy_file_dir = os.path.join(data_dir, case_id, "buggy_files")
        for file_name in os.listdir(buggy_file_dir):
            if not file_name.endswith(".py"):
                continue
            buggy_file_path = os.path.join(buggy_file_dir, file_name)
            print(buggy_file_path)
            solved_entities = extract_and_print_entities(buggy_file_path)
            output_dir = os.path.join(data_dir, case_id, "entities")
            os.makedirs(output_dir, exist_ok=True)
            entity_file_name = file_name[:-3] + ".json"
            with open(os.path.join(output_dir, entity_file_name), "w") as file:
                json.dump(solved_entities, file, indent=4)