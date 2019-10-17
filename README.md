# Label Manager Action

## Overview

A simple label manager that syncs a JSON file with labels with your repository. Labels are either added if they don't
exist, or edited if they do exist and the description or color have changed. Optionally, labels not in the list will be
deleted if `mode` is set to `delete` (default is `normal`).

```yml
name: labels

on:
  push:
    branches:
      - 'master'

jobs:
  label-sync:

    runs-on: ubuntu-latest

    steps:
    - uses: actions/checkout@v1
    - name: Sync labels
      uses: facelessuser/label-mgr-action@v1
      with:
        token: ${{ secrets.GH_TOKEN }}
```

By default, labels are looked for in `.github/labels.json`, but if you'd like to store them elsewhere, you can use the
`file` option.

```yml
name: labels

on:
  push:
    branches:
      - 'master'

jobs:
  label-sync:

    runs-on: ubuntu-latest

    steps:
    - uses: actions/checkout@v1
    - name: Sync labels
      uses: facelessuser/label-mgr-action@v1
      with:
        token: ${{ secrets.GH_TOKEN }}
        mode: 'delete'
        file: 'alternate/location/labels.json'
```

## JSON Label Format

Labels are stored in a list:

```js
{
    "labels": {
        "bug": {"color": "#ff0000", "description": "Bug report."},
        "feature": {"color": "#00ff00", "description": "Feature request."}
    }
}

```

You can also predefine color variables. This is useful if you wish to reuse a color for multiple labels.

```js
{
    "colors": {
        "bug": "#ff0000",
        "feature": "#00ff00"
    },
    "labels": {
        "bug": {"color": "bug", "description": "Bug report."},
        "feature": {"color": "feature", "description": "Feature request."}
    }
}
```

You can also specify a label to be renamed. This is useful if you want to change the name of a label that is present on
existing issues. Simply create an entry using the the new name, and add the old named under `renamed`. So if we had
a label called `bug`, and we wanted to add a :bug: emoji to the name:

```js
{
    "labels": {
        "bug :bug:": {"renamed": "bug", "color": "#ff0000", "description": "Bug report."}
    }
}
```

When `mode` is set to `delete`, there may be certain labels you wish to ignore. Maybe they are created by an external
process like `dependbot`.  Simply add labels you wish to ignore to the the ignore list:

```js
{
    "colors": {
        "bug": "#ff0000",
        "feature": "#00ff00"
    },
    {
      "ignores": [
        "dependencies",
        "security"
      ]
    },
    "labels": {
        "bug": {"color": "bug", "description": "Bug report."},
        "feature": {"color": "feature", "description": "Feature request."}
    }
}
```

## YAML Format

If desired, you can point to a YAML file instead. Label-mgr-action can actually parse both formats. All of the same
features available in the JSON format are available in the YAML format. Just make sure to use `file` to point to your
YAML file.

```yml
labels:
    bug:
        color: '#ff0000'
        description: Bug report.
    feature:
        color: '#00ff00'
        description: Feature request.
```
