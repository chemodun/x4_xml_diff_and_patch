import argparse
from lxml import etree
import sys
import os
import re
import logging

def get_input(prompt):
    return input(prompt)

def parse_arguments():
    parser = argparse.ArgumentParser(description='Apply XML diff to original XML or directory.')
    parser.add_argument('original_xml', nargs='?', help='Path to the original XML file or directory')
    parser.add_argument('diff_xml', nargs='?', help='Path to the diff XML file or directory')
    parser.add_argument('output_xml', nargs='?', help='Path for the output XML file or directory')
    parser.add_argument('--xsd', dest='diff_xsd', help='Path to the diff.xsd schema file.', default=None)
    args = parser.parse_args()

    if not args.original_xml:
        args.original_xml = get_input('Enter path to original XML file  or directory: ').strip()
    if not args.diff_xml:
        args.diff_xml = get_input('Enter path to diff XML file or directory: ').strip()
    if not args.output_xml:
        args.output_xml = get_input('Enter path for output XML file  or directory: ').strip()

    # Convert to absolute paths
    args.original_xml = os.path.abspath(args.original_xml)
    args.diff_xml = os.path.abspath(args.diff_xml)
    args.output_xml = os.path.abspath(args.output_xml)
    args.diff_xsd = os.path.abspath(args.diff_xsd) if args.diff_xsd else None

    return args.original_xml, args.diff_xml, args.output_xml, args.diff_xsd

def validate_diff_xml(diff_xml_path, xsd_path):
    """
    Validates the diff XML against the provided XSD schema.

    Args:
        diff_xml_path (str): Path to the diff XML file.
        xsd_path (str): Path to the diff.xsd schema file.

    Returns:
        bool: True if validation is successful, False otherwise.
    """
    try:
        with open(xsd_path, 'rb') as f:
            xmlschema_doc = etree.parse(f)
            xmlschema = etree.XMLSchema(xmlschema_doc)
    except Exception as e:
        logging.error(f"Error parsing diff.xsd: {e}")
        return False

    try:
        with open(diff_xml_path, 'rb') as f:
            diff_doc = etree.parse(f)
    except Exception as e:
        logging.error(f"Error parsing diff.xml: {e}")
        return False

    if not xmlschema.validate(diff_doc):
        logging.error(f"diff.xml '{diff_xml_path}' is not valid against diff.xsd. Patch will not be applied.")
        for error in xmlschema.error_log:
            logging.error(f"Line {error.line}: {error.message}")
        return False
    else:
        logging.info(f"diff.xml '{diff_xml_path}' is valid against diff.xsd.")
        return True

def detect_indentation(xml_path):
    """
    Detects the per-level indentation used in the given XML file.

    Args:
        xml_path (str): Path to the XML file.

    Returns:
        str: The per-level indentation string (e.g., '    ' for four spaces or '\t' for a tab).
    """
    indentation_levels = set()
    indent_pattern = re.compile(r'^(\s+)<')

    with open(xml_path, 'r', encoding='utf-8') as file:
        for line in file:
            match = indent_pattern.match(line)
            if match:
                indent = match.group(1)
                indentation_levels.add(indent)

    if not indentation_levels:
        return '    '  # Default to four spaces if no indentation found

    # Convert indentation levels to lengths
    sorted_indents = sorted(indentation_levels, key=lambda x: len(x))

    # Find the smallest non-zero indentation increment
    indent_lengths = sorted([len(indent) for indent in sorted_indents if len(indent) > 0])

    # Calculate differences between consecutive indent lengths
    differences = [
        indent_lengths[i] - indent_lengths[i - 1]
        for i in range(1, len(indent_lengths))
        if indent_lengths[i] - indent_lengths[i - 1] > 0
    ]

    if differences:
        per_level_indent_len = min(differences)
    else:
        # If differences list is empty, assume per-level indent is the smallest indented level
        per_level_indent_len = len(sorted_indents[0])

    # Identify the indent string with length equal to per_level_indent_len
    for indent in sorted_indents:
        if len(indent) == per_level_indent_len:
            per_level_indent = indent
            break
    else:
        # Fallback if no exact match found
        per_level_indent = '    '

    return per_level_indent

def apply_add(diff_element, original_root):
    sel = diff_element.get('sel')
    pos = diff_element.get('pos', 'after')
    new_elements = list(diff_element)

    target_nodes = original_root.xpath(sel)
    if not target_nodes:
        logging.warning(f"No nodes found for add selector: {sel}")
        return

    for target in target_nodes:
        for new_element in new_elements:
            # Copy the new element to avoid modifying the original
            new_elem_str = etree.tostring(new_element, encoding='utf-8').decode('utf-8')
            # Remove the namespace declaration from the new element
            clean_new_elem_str = re.sub(r'\sxmlns:xsi=".*?"', '', new_elem_str)
            # Parse the cleaned new element
            try:
                new_elem = etree.fromstring(clean_new_elem_str)
            except etree.XMLSyntaxError as e:
                logging.error(f"Failed to parse cleaned new element: {e}")
                continue

            # Insert based on position
            parent = target.getparent()
            if parent is not None:
                if pos == 'before':
                    parent.insert(parent.index(target), new_elem)
                    logging.info(f"Added new element '{new_elem.tag}' before '{target.tag}' in '{parent.tag}'.")
                elif pos == 'after':
                    parent.insert(parent.index(target) + 1, new_elem)
                    logging.info(f"Added new element '{new_elem.tag}' after '{target.tag}' in '{parent.tag}'.")
                elif pos == 'prepend':
                    parent.insert(0, new_elem)
                    logging.info(f"Prepended new element '{new_elem.tag}' to '{parent.tag}'.")
                else:
                    logging.warning(f"Unknown position: {pos}. Skipping insertion.")

def apply_replace(diff_element, original_root):
    """
    Applies the 'replace' operation defined in the diff XML to the original XML.

    Args:
        diff_element (etree.Element): The <replace> element containing replace operations.
        original_root (etree.Element): The root of the original XML tree.
    """
    sel = diff_element.get('sel')
    if sel is None:
        logging.warning("Replace operation missing 'sel' attribute.")
        return

    new_content = diff_element.text  # For text replacement
    new_element = diff_element.find('new')  # For element replacement

    target_nodes = original_root.xpath(sel)
    if not target_nodes:
        logging.warning(f"No nodes found for replace selector: {sel}")
        return

    for node in target_nodes:
        if isinstance(node, etree._Element):
            if new_content is not None:
                # Replace element text
                original_text = node.text
                node.text = new_content
                logging.debug(f"Replaced text of element '{node.tag}' from '{original_text}' to '{new_content}'.")
            elif new_element is not None:
                # Replace entire element with new_element subtree
                try:
                    replacement = etree.fromstring(etree.tostring(new_element, encoding='utf-8'))
                    parent = node.getparent()
                    if parent is not None:
                        parent.replace(node, replacement)
                        logging.info(f"Replaced element '{node.tag}' with '{replacement.tag}'.")
                except etree.XMLSyntaxError as e:
                    logging.error(f"Invalid XML in <new> element: {e}")
            else:
                logging.warning(f"No replacement content provided for selector: {sel}")
        elif isinstance(node, etree._ElementUnicodeResult):
            # Replacing an attribute value
            parent = node.getparent()
            attr = node.attrname
            original_value = parent.get(attr)
            parent.set(attr, new_content)
            logging.debug(f"Replaced attribute '{attr}' of element '{parent.tag}' from '{original_value}' to '{new_content}'.")
        else:
            logging.warning(f"Unsupported node type for replacement: {type(node)}")

def apply_remove(diff_element, original_root):
    """
    Applies the 'remove' operation defined in the diff XML to the original XML.

    Args:
        diff_element (etree.Element): The <remove> element containing remove operations.
        original_root (etree.Element): The root of the original XML tree.
    """
    sel = diff_element.get('sel')
    if sel is None:
        logging.warning("Remove operation missing 'sel' attribute.")
        return

    target_nodes = original_root.xpath(sel)
    if not target_nodes:
        logging.warning(f"No nodes found for remove selector: {sel}")
        return

    for node in target_nodes:
        parent = node.getparent()
        if parent is None:
            logging.warning(f"Cannot remove root element '{node.tag}'. Skipping.")
            continue

        # Remove the node
        parent.remove(node)
        logging.debug(f"Removed element '{node.tag}' from '{parent.tag}'.")

        # Adjust indentation
        # If the removed node had a tail with indentation, propagate it to the previous sibling or parent
        if node.tail and node.tail.strip() == '':
            index = parent.index(node) if node in parent else -1
            if index > 0:
                # Get the previous sibling
                prev_sibling = parent[index - 1]
                if prev_sibling.tail is not None:
                    # Append the removed node's tail to the previous sibling's tail
                    prev_sibling.tail += node.tail
                else:
                    prev_sibling.tail = node.tail
            else:
                # If there is no previous sibling, adjust the parent's text or tail
                if parent.text is not None:
                    parent.text += node.tail
                else:
                    parent.text = node.tail

        # Optional: Clean stray whitespace
        clean_whitespace(parent)

def clean_whitespace(parent):
    """
    Cleans up stray whitespace in the XML tree after removal operations.

    Args:
        parent (etree.Element): The parent element whose children may have stray whitespace.
    """
    if len(parent) > 0:
        # Ensure the last child has a tail with proper indentation
        last_child = parent[-1]
        if not last_child.tail or last_child.tail.strip() != '':
            last_child.tail = '\n' + '    ' * (get_element_level(last_child) - 1)
    else:
        # If the parent has no children, adjust its text
        if not parent.text or parent.text.strip() != '':
            parent.text = '\n' + '    ' * (get_element_level(parent) - 1)

def get_element_level(element):
    """
    Determines the depth level of an element in the XML tree.

    Args:
        element (etree.Element): The element whose level is to be determined.

    Returns:
        int: The depth level of the element (root is 0).
    """
    level = 0
    parent = element.getparent()
    while parent is not None:
        level += 1
        parent = parent.getparent()
    return level

def process_single_file(original_file, diff_file, output_file, diff_xsd_path):
    """
    Processes a single trio of original, diff, and output files.

    Args:
        original_file (str): Path to the original XML file.
        diff_file (str): Path to the diff XML file.
        output_file (str): Path where the patched XML will be saved.
        diff_xsd_path (str): Path to the diff.xsd schema file.

    Returns:
        None
    """
    # Validate the diff file
    if not validate_diff_xml(diff_file, diff_xsd_path):
        logging.error(f"Validation failed for diff file '{diff_file}'. Skipping.")
        return

    # Parse the original XML file
    try:
        original_tree = etree.parse(original_file)
        logging.info(f"Parsed original XML: {original_file}")
    except Exception as e:
        logging.error(f"Error parsing original XML '{original_file}': {e}")
        return

    # Parse the diff XML file
    try:
        parser = etree.XMLParser(remove_blank_text=False)
        diff_tree = etree.parse(diff_file, parser)
        logging.info(f"Parsed diff XML: {diff_file}")
    except Exception as e:
        logging.error(f"Error parsing diff XML '{diff_file}': {e}")
        return

    # Detect indentation
    indent_str = detect_indentation(original_file)
    logging.info(f"Detected indentation for '{original_file}': '{repr(indent_str)}'")

    # Get the root element of the diff XML
    diff_root = diff_tree.getroot()

    # Apply each operation in the diff XML
    for operation in diff_root:
        if operation.tag == 'add':
            apply_add(operation, original_tree.getroot())
        elif operation.tag == 'replace':
            apply_replace(operation, original_tree.getroot())
        elif operation.tag == 'remove':
            apply_remove(operation, original_tree.getroot())
        else:
            logging.warning(f"Unknown operation: {operation.tag} in diff file '{diff_file}'. Skipping.")

    # Determine the output directory
    output_dir = os.path.dirname(output_file)

    # If the output path is a directory, append the original file name
    if os.path.isdir(output_file):
        output_dir = output_file
        output_file = os.path.join(output_dir, os.path.basename(original_file))

    # Ensure the output directory exists
    if output_dir and not os.path.exists(output_dir):
        try:
            os.makedirs(output_dir)
            logging.info(f"Created output directory: {output_dir}")
        except Exception as e:
            logging.error(f"Failed to create output directory '{output_dir}': {e}")
            return

    # Re-indent the entire XML tree for consistent formatting
    if hasattr(etree, 'indent'):
        etree.indent(original_tree, space=indent_str)
        logging.info(f"Applied indentation to the output XML tree for '{output_file}'.")

    # Write the patched XML to the output file
    try:
        original_tree.write(output_file, pretty_print=True, xml_declaration=True, encoding='utf-8')
        logging.info(f"Patched XML successfully written to '{output_file}'.")
    except Exception as e:
        logging.error(f"Error writing patched XML to '{output_file}': {e}")

def main():
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )

    original_path, diff_path, output_path, diff_xsd_path = parse_arguments()

    # Determine the path to diff.xsd
    if diff_xsd_path:
        if not os.path.isfile(diff_xsd_path):
            logging.error(f"diff.xsd file does not exist: {diff_xsd_path}")
            sys.exit(1)
        else:
            logging.info(f"Using provided diff.xsd path: {diff_xsd_path}")
    else:
        # Look for 'diff.xsd' in the same directory as the script
        script_dir = os.path.dirname(os.path.abspath(__file__))
        default_xsd_path = os.path.join(script_dir, 'diff.xsd')
        if os.path.isfile(default_xsd_path):
            diff_xsd_path = default_xsd_path
            logging.info(f"Using default diff.xsd path: {diff_xsd_path}")
        else:
            logging.error("diff.xsd not provided and not found in the script's directory.")
            sys.exit(1)

    # Determine if original, diff, and output are directories or files
    original_is_dir = os.path.isdir(original_path)
    diff_is_dir = os.path.isdir(diff_path)
    output_is_dir = os.path.isdir(output_path)

    if original_is_dir and diff_is_dir and output_is_dir:
        logging.info("original, Diff, and Output paths are all directories. Processing multiple files.")

        # Traverse the diff directory
        for root, dirs, files in os.walk(diff_path):
            for file in files:
                if file.lower().endswith('.xml'):
                    diff_file_path = os.path.join(root, file)
                    # Determine the relative path
                    rel_path = os.path.relpath(diff_file_path, diff_path)
                    original_file_path = os.path.join(original_path, rel_path)
                    output_file_path = os.path.join(output_path, rel_path)

                    if not os.path.isfile(original_file_path):
                        logging.warning(f"original file does not exist for diff file '{diff_file_path}'. Skipping.")
                        continue

                    # Process the single trio of diff, original, and output
                    process_single_file(original_file_path, diff_file_path, output_file_path, diff_xsd_path)

    else:
        if original_is_dir or diff_is_dir:
            logging.error("If one of original, diff is a directory, both must be directories.")
            sys.exit(1)

        logging.info("original, Diff, and Output paths are all files. Processing single file.")

        original_xml_path = original_path
        diff_xml_path = diff_path
        output_xml_path = output_path

        # Process the single trio of diff, original, and output
        process_single_file(original_xml_path, diff_xml_path, output_xml_path, diff_xsd_path)

if __name__ == "__main__":
    main()