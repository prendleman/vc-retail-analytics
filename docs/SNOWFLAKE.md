# AQ Snowflake setup — VC Retail Analytics

Isolated database: **VC_RETAIL_DEMO** (do not reuse RELIEF_DEMO objects).

## Profiles (local `~/.snowflake/connections.toml` — never commit)

```toml
[aq]
account = "YOUR_AQ_ORG-YOUR_AQ_ACCOUNT"
user = "YOUR_AQ_DEMO_OWNER"
authenticator = "externalbrowser"

[aq_vc_reader]
account = "YOUR_AQ_ORG-YOUR_AQ_ACCOUNT"
user = "YOUR_AQ_READER_USER"
authenticator = "externalbrowser"
role = "AQ_VC_READER"
warehouse = "AQ_VC_RETAIL_WH"
database = "VC_RETAIL_DEMO"
schema = "SERVING"
```

## Ordered setup

```sh
python3 -m pip install -r requirements-cloud.txt
python3 -m scripts.seed
python3 -m scripts.cloud doctor --connection aq
python3 -m scripts.cloud platform --connection aq
python3 -m scripts.cloud load --connection aq
python3 -m scripts.cloud transform --connection aq
python3 -m scripts.cloud governance --connection aq
python3 -m scripts.cloud semantic --connection aq
python3 -m scripts.cloud validate --connection aq
python3 -m scripts.cloud reconcile --connection aq
```

Grant `AQ_VC_READER` to the reader principal and insert `CURRENT_USER()` → `DLR-0001` (or `*`) into `GOVERNANCE.USER_DEALERS`.

```sh
python3 -m app.server --backend snowflake --connection aq_vc_reader
```

Cortex (optional): set `SNOWFLAKE_HOST` + `SNOWFLAKE_PAT`, then `python3 -m scripts.cortex "What is net sales by channel?"`.
