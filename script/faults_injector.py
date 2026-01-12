#!/usr/bin/env python3
"""
Main script for injecting faults into SMV models
"""

import sys
import re
from xml_parser import parse_fault_model
from smv_utils import load_smv, save_smv, find_module


class StuckAtInjector:
    """Handles 'stuck-at' fault injection into a module."""    
    def __init__(self, faults):
        self.faults = faults

    
    def get_fault_mode_enum(self):
        """Generate the fault_mode enum values"""
        modes = ['none']
        
        for fault in self.faults:
            mode_name = f"stuck_{fault.value}"
            if mode_name not in modes:
                modes.append(mode_name)
        return ', '.join(modes)
    

    def inject_into_module(self, module_text):
        """
        Inject fault_mode variable and modify assignments.
        Returns modified module text.
        """
        lines = module_text.splitlines(keepends=True)
        
        # Find VAR section
        var_idx = self._find_section_start(lines, "VAR")
        if var_idx is None:
            raise ValueError("No VAR section found in module")
        
        # Insert fault_mode variable after VAR
        fault_mode_decl = f"    fault_mode : {{{self.get_fault_mode_enum()}}};\n"
        lines.insert(var_idx + 1, fault_mode_decl)
        
        # Find ASSIGN section
        assign_idx = self._find_section_start(lines, "ASSIGN")
        if assign_idx is None:
            raise ValueError("No ASSIGN section found in module")
        
        # Insert init(fault_mode)
        init_fault = "    init(fault_mode) := none;\n\n"
        lines.insert(assign_idx + 1, init_fault)
        
        # Insert next(fault_mode) 
        next_fault = self._generate_next_fault_mode()
        insert_pos = self._find_insert_position_for_next_fault_mode(lines, assign_idx)
        lines.insert(insert_pos, next_fault)
        
        # Modify existing next() assignments to add fault conditions
        modified_text = ''.join(lines)
        modified_text = self._inject_fault_conditions(modified_text)
        
        return modified_text
    
    def _find_section_start(self, lines, keyword):
        """Find the line index where a section (VAR, ASSIGN, etc.) starts"""
        for i, line in enumerate(lines):
            if line.strip().startswith(keyword):
                return i
        return None
    
    def _find_insert_position_for_next_fault_mode(self, lines, assign_idx):
        """Find where to insert next(fault_mode) - after init statements"""
        # Look for the last init() statement after ASSIGN
        last_init_idx = assign_idx
        for i in range(assign_idx + 1, len(lines)):
            if 'init(' in lines[i]:
                last_init_idx = i
            elif 'next(' in lines[i]:
                # Found first next(), insert before it
                return i
        # If no next() found, insert after last init
        return last_init_idx + 1
    
    def _generate_next_fault_mode(self):
        """Generate the next(fault_mode) assignment"""
        choices = self.get_fault_mode_enum()
        return f"""    next(fault_mode) :=
        case
            fault_mode = none :
                {{{choices}}};
            TRUE :
                fault_mode;
        esac;
"""
    
    def _inject_fault_conditions(self, module_text):
        """Inject fault conditions into next() assignments"""
        # Group faults by variable
        faults_by_var = {}
        for fault in self.faults:
            if fault.variable not in faults_by_var:
                faults_by_var[fault.variable] = []
            faults_by_var[fault.variable].append(fault)
        
        # Inject into each affected variable's next() assignment
        for variable, var_faults in faults_by_var.items():
            module_text = self._inject_into_next_assignment(module_text, variable, var_faults)
        
        return module_text
    
    def _inject_into_next_assignment(self, text, variable, faults):
        """Inject fault conditions at the start of a next(variable) case statement"""
        # Pattern: next(variable) := case ... esac;
        pattern = rf'(next\({re.escape(variable)}\)\s*:=\s*case)(.*?)(esac;)'
        match = re.search(pattern, text, re.DOTALL)
        
        if not match:
            raise ValueError(f"Could not find next({variable}) assignment")
        
        prefix = match.group(1)
        original_cases = match.group(2)
        suffix = match.group(3)
        
        # Build fault condition cases
        fault_cases = "\n"
        for fault in faults:
            mode_name = f"stuck_{fault.value}"
            fault_cases += f"        fault_mode = {mode_name} : {fault.value};\n"
        
        # Reconstruct with fault cases first
        new_assignment = f"{prefix}{fault_cases}{original_cases}    {suffix}"
        
        return text[:match.start()] + new_assignment + text[match.end():]
    
    def protect_toggle_logic(self, module_text):
        """
        Protect request_toggle from changing when faults are active.
        """
        # Find next(request_toggle) and add fault_mode = none condition
        pattern = r'(next\(request_toggle\)\s*:=\s*case)(.*?)(esac;)'
        match = re.search(pattern, module_text, re.DOTALL)
        
        if not match:
            return module_text  # no request_toggle in this module
        
        prefix = match.group(1)
        original_cases = match.group(2)
        suffix = match.group(3)
        
        # Check if we need to add fault_mode = none to existing condition
        # Look for patterns like: "server_state = receiving & !queue.empty : !request_toggle"
        
        # We'll add fault_mode = none to the condition that toggles
        lines = original_cases.split('\n')
        new_cases = []
        
        for line in lines:
            # If this line toggles the bit (contains !request_toggle on RHS)
            if '!request_toggle' in line and ':' in line:
                # Extract the condition part (before the colon)
                parts = line.split(':', 1)
                condition = parts[0].strip()
                action = parts[1].strip()
                
                # Add fault_mode = none to the condition
                new_condition = f"fault_mode = none &\n        {condition}"
                new_cases.append(f"        {new_condition} : {action}\n")
            else:
                new_cases.append(line + '\n')
        
        new_assignment = f"{prefix}{''.join(new_cases)}    {suffix}"
        
        return module_text[:match.start()] + new_assignment + module_text[match.end():]


class FaultInjectionEngine:
    """
    Main engine that coordinates fault injection.
    """
    def __init__(self, fault_model):
        self.fault_model = fault_model
        self.injector = self._create_injector()
    
    def _create_injector(self):
        # Check what types of faults we have
        fault_types = set(f.type for f in self.fault_model.faults)
        
        if fault_types == {'stuck-at'}:
            return StuckAtInjector(self.fault_model.faults)
        else:
            raise ValueError(f"Unsupported fault type(s): {fault_types}")
    

    def inject(self, smv_content):
        # Find the target module
        start_idx, end_idx = find_module(smv_content, self.fault_model.target_module)
        
        lines = smv_content.splitlines(keepends=True)
        module_lines = lines[start_idx:end_idx]
        module_text = ''.join(module_lines)

        # Inject faults
        modified_module = self.injector.inject_into_module(module_text)
        
        # Protect toggle logic if needed
        modified_module = self.injector.protect_toggle_logic(modified_module)   # TODO: this case becomes too specific for each case
        
        # Replace in original content
        new_content = ''.join(lines[:start_idx]) + modified_module + ''.join(lines[end_idx:])
        
        return new_content
    
    def replicate_for_redundancy(self, smv_content):
        """Create redundant instances of the target module in Nominal Model."""
        if self.fault_model.redundancy <= 1:
            return smv_content
        
        # Find NominalR module
        try:
            start_idx, end_idx = find_module(smv_content, "NominalR")   # TODO: should this nominal wrapper be a thing across all models?
        except ValueError:
            print("Warning: NominalR module not found, skipping redundancy")
            return smv_content
        
        lines = smv_content.splitlines(keepends=True)
        nominal_lines = lines[start_idx:end_idx]
        
        # Find the instance declaration for target module
        target_lower = self.fault_model.target_module.lower()
        
        new_nominal = []
        found_target = False
        
        for line in nominal_lines:
            # Check if this line declares an instance of the target module
            if f': process {self.fault_model.target_module}' in line:
                found_target = True
                # Extract the pattern: "instance_name : process Module(params);"
                match = re.match(r'(\s*)(\w+)\s*:\s*process\s+(\w+)\((.*?)\);', line)
                if match:
                    indent = match.group(1)
                    instance_name = match.group(2)
                    module_name = match.group(3)
                    params = match.group(4)
                    
                    # Create multiple instances
                    for i in range(1, self.fault_model.redundancy + 1):
                        new_instance = f"{indent}{instance_name}_{i} : process {module_name}({params});\n"
                        new_nominal.append(new_instance)
                else:
                    # Couldn't parse, keep original
                    new_nominal.append(line)
            else:
                new_nominal.append(line)
        
        if not found_target:
            print(f"Warning: Could not find instance of {self.fault_model.target_module} in NominalR")
            return smv_content
        
        # Replace NominalR
        new_content = ''.join(lines[:start_idx]) + ''.join(new_nominal) + ''.join(lines[end_idx:])
        
        return new_content


def main():
    if len(sys.argv) != 4:
        print("Usage: python inject_faults.py <input.smv> <faults.xml> <output.smv>")
        sys.exit(1)
    
    input_smv = sys.argv[1]
    faults_xml = sys.argv[2]
    output_smv = sys.argv[3]
    
    print("=" * 60)
    print("SMV Fault Injection Tool")
    print("=" * 60)
    
    # Parse fault specification
    print(f"\n[1] Parsing fault specification: {faults_xml}")
    fault_model = parse_fault_model(faults_xml)
    print(f"    Target module: {fault_model.target_module}")
    print(f"    Redundancy: {fault_model.redundancy}")
    print(f"    Faults: {len(fault_model.faults)}")
    for f in fault_model.faults:
        print(f"      - {f.type} on {f.variable} = {f.value}")
    
    # Load SMV model
    print(f"\n[2] Loading SMV model: {input_smv}")
    smv_content = load_smv(input_smv)
    
    # Create injection engine
    print(f"\n[3] Initializing fault injection engine")
    engine = FaultInjectionEngine(fault_model)
    
    # Inject faults
    print(f"\n[4] Injecting faults")
    modified_content = engine.inject(smv_content)
    
    # Handle redundancy
    if fault_model.redundancy > 1:
        print(f"\n[5] Creating redundant instances")
        modified_content = engine.replicate_for_redundancy(modified_content)
    
    # Save result
    print(f"\n[6] Saving extended model: {output_smv}")
    save_smv(output_smv, modified_content)
    
    print("\n" + "=" * 60)
    print("Fault injection complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()