# AI Decision Engine for Business Data

Ask business questions in plain English. The system generates a read-only SQL query, runs it,
charts the result, and recommends actions, each traceable to the query and rows behind it.

## Setup
```bash
pip install -r requirements.txt
cp .env.example .env        # add your GEMINI_API_KEY
# put your CSV files in ./data, then:
python load_data.py
streamlit run app.py
```

## Tests
```bash
pytest
```

## AI tools used
- (list every AI tool you used, e.g. coding assistant, LLM API + model)
