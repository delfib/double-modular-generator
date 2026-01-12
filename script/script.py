from xml_parser import parse_fault_model
from smv_utils import *

def inject_stuck_at(module_text, fault):
    """
    fault.variable: variable name to affect
    fault.value: stuck value
    """

    lines = module_text.splitlines(keepends=True)
    out = []

    inserted_var = False
    inserted_assign = False

    for line in lines:
        out.append(line)

        # Insert fault_mode variable after VAR
        if line.strip() == "VAR" and not inserted_var:
            out.append("    fault_mode : {none, stuck};\n")
            inserted_var = True

        # Insert ASSIGN logic
        if line.strip() == "ASSIGN" and not inserted_assign:
            out.append(
                f"    next({fault.variable}) := "
                f"case fault_mode = stuck : {fault.value}; "
                f"TRUE : {fault.variable}; esac;\n"
            )
            inserted_assign = True

    if not inserted_var or not inserted_assign:
        raise ValueError("Failed to inject stuck-at fault")

    return "".join(out)

FAULT_INJECTORS = {
    "stuck_at": inject_stuck_at,
}

def inject_faults(xml_path, output_path):
    spec = parse_fault_model(xml_path)

    smv_content = load_smv(spec.model_file)

    start, end = find_module(smv_content, spec.target_module)

    lines = smv_content.splitlines(keepends=True)
    module_text = "".join(lines[start:end])

    # Apply faults one by one
    for fault in spec.faults:
        if fault.type not in FAULT_INJECTORS:
            raise ValueError(f"Unknown fault type: {fault.type}")

        injector = FAULT_INJECTORS[fault.type]
        module_text = injector(module_text, fault)

    # Rebuild SMV file
    new_content = (
        "".join(lines[:start]) +
        module_text +
        "".join(lines[end:])
    )

    save_smv(output_path, new_content)
