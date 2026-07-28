# Low-level access

The high-level object graph should cover normal analysis. Use raw member access when you need bytes that the SDK deliberately does not interpret.

## List archive members

```python
with open_export("project.zip") as export:
    for path in sorted(export.members):
        print(path)
```

## Read one member

```python
with open_export("project.zip") as export:
    artifact = export.member("manifest.json")
    with artifact.open() as stream:
        payload = stream.read()
```

Each `open()` call returns an independent in-memory binary stream. The SDK never extracts a ZIP to disk.

## Keep the safety boundary

Do not use raw access to bypass validation or to load NumPy object arrays. If a supported v2 member is missing from the high-level API, open an issue rather than depending on private modules such as `neuroqp._reader`.
