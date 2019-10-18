# Label Manager Action

## Overview

A simple label manager that syncs a YAML file with labels with your repository. Labels are either added if they don't
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

By default, labels are looked for in `.github/labels.yml`, but if you'd like to store them elsewhere, you can use the
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
        file: 'alternate/location/labels.yml'
```

## YAML Label Format

Labels are stored in a list:

```js
labels:
- name: bug
  color: bug
  description: Bug report.

- name: feature
  color: feature
  description: Feature request.

```

You can also predefine color variables. This is useful if you wish to reuse a color for multiple labels.

```js
colors:
  bug: '#c45b46'

labels:
- name: bug
  color: bug
  description: Bug report.

- name: feature
  color: feature
  description: Feature request.
```

You can also specify a label to be renamed. This is useful if you want to change the name of a label that is present on
existing issues. Simply create an entry using the the new name, and add the old named under `renamed`. So if we had
a label called `bug`, and we wanted to add a :bug: emoji to the name:

```js
labels:
- name: 'bug :bug:'
  renamed: bug
  color: bug
  description: Bug report.
```

When `mode` is set to `delete`, there may be certain labels you wish to ignore. Maybe they are created by an external
process like `dependbot`.  Simply add labels you wish to ignore to the the ignore list:

```js
colors:
  bug: '#c45b46'

ignores:
- dependencies
- security

labels:
- name: bug
  color: bug
  description: Bug report.

- name: feature
  color: feature
  description: Feature request.
```
