## Generating the extended version of the nominal model R_Protocol.smv

### Create and activate a Python Virtual Environment
```
python3 -m venv venv
source venv/bin/activate
```

### Install required dependencies 
```
pip install antlr4-python3-runtime==4.9.2
pip install lxml
```


### Generate the extended model
```python3 ../../xSAP-1.5.0/xSAP/scripts/extend_model.py -v R_Protocol.smv R_Protocol.fei```
