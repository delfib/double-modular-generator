set on_failure_script_quits
read_model -i "R_Protocol.smv"
flatten_hierarchy
fe_load_doc -o "out/errors.log"  -p "/home/delfina/Downloads/xSAP-1.5.0/xSAP/data/schema" -i "out/expanded_R_Protocol.xml"
fe_extend_module -m "out/fms_R_Protocol.xml"   -o "out/extended_R_Protocol.smv"
quit
