# wowusky manifest registry

wowusky uses manifests for metadata only. Manifests can add or override addon
entries without mirroring ZIP files or scraping websites.

User manifests live in:

```text
~/.local/share/wowusky/manifests/*.json
```

Example:

```json
{
  "addons": [
    {
      "id": "example-addon",
      "name": "Example Addon",
      "provider": "github",
      "repo": "owner/repo",
      "category": "Interface",
      "flavors": ["retail", "mainline"],
      "folders": ["ExampleAddon"],
      "description": "Short description."
    }
  ]
}
```
