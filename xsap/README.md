### Generating the extended version of the nominal model R_Protocol.smv
```
python3 -m venv venv
source venv/bin/activate
pip install antlr4-python3-runtime==4.9.2
pip install lxml
```

```python3 ../../xSAP-1.5.0/xSAP/scripts/extend_model.py -v R_Protocol.smv R_Protocol.fei```
