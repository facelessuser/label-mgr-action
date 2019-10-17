#!/usr/bin/env python
"""Populate GitHub labels for issue tracker."""
from collections import namedtuple
import codecs
import yaml
import json
import sys
import os
import re
import requests
import urllib.parse
try:
    from yaml import CLoader as Loader
except ImportError:
    from yaml import Loader

__version__ = "1.0.0"

RE_VALID_COLOR = re.compile('#[a-fA-F0-9]{6}')


class Api:
    """Class to post commands to the REST API."""

    def __init__(self, token, user, repo):
        """Initialize."""

        self.url = 'https://api.github.com/'
        self.token = token
        self.user = user
        self.repo = repo

    def _delete(self, command, timeout=60):
        """Send a DELETE REST command."""

        if timeout == 0:
            timeout = None

        headers = {
            'Authorization': 'token {}'.format(self.token),
            'Accept': 'application/vnd.github.symmetra-preview+json'
        }

        try:
            resp = requests.delete(
                self.url + command,
                headers=headers,
                timeout=timeout
            )

            assert resp.status_code == 204

        except Exception:
            raise RuntimeError('DELETE command failed: {}'.format(self.url + command))

    def _patch(self, command, payload, timeout=60):
        """Send a PATCH REST command."""

        if timeout == 0:
            timeout = None

        headers = {
            'Authorization': 'token {}'.format(self.token),
            'Accept': 'application/vnd.github.symmetra-preview+json'
        }

        if payload is not None:
            payload = json.dumps(payload)
            headers['content-type'] = 'application/json'

        try:
            resp = requests.patch(
                self.url + command,
                data=payload,
                headers=headers,
                timeout=timeout
            )

            assert resp.status_code == 200

        except Exception:
            raise RuntimeError('PATCH command failed: {}'.format(self.url + command))

    def _post(self, command, payload, timeout=60):
        """Send a POST REST command."""

        if timeout == 0:
            timeout = None

        headers = {
            'Authorization': 'token {}'.format(self.token),
            'Accept': 'application/vnd.github.symmetra-preview+json'
        }

        if payload is not None:
            payload = json.dumps(payload)
            headers['content-type'] = 'application/json'

        try:
            resp = requests.post(
                self.url + command,
                data=payload,
                headers=headers,
                timeout=timeout
            )

            assert resp.status_code == 201

        except Exception:
            raise RuntimeError('POST command failed: {}'.format(self.url + command))

    def _get(self, command, timeout=60, pages=False):
        """Send a GET REST request."""

        if timeout == 0:
            timeout = None

        headers = {
            'Authorization': 'token {}'.format(self.token),
            'Accept': 'application/vnd.github.symmetra-preview+json'
        }

        cmd = self.url + command
        data = None

        while cmd:
            try:
                resp = requests.get(
                    cmd,
                    headers=headers,
                    timeout=timeout
                )

                assert resp.status_code == 200

                cmd = resp.links.get('next', {}).get('url', '') if pages else ''
                if pages and data is not None:
                    data.extend(json.loads(resp.text))
                else:
                    data = json.loads(resp.text)
            except Exception:
                raise RuntimeError('GET command failed: {}'.format(cmd))

        return data

    def get_labels(self):
        """Get labels."""

        return self._get('/'.join(['repos', self.user, self.repo, 'labels']), pages=True)

    def create_label(self, name, color, description):
        """Create label."""

        self._post(
            '/'.join(['repos', self.user, self.repo, 'labels']),
            {'name': name, 'color': color, 'description': description}
        )

    def edit_label(self, old_name, new_name, color, description):
        """Edit label."""

        self._patch(
            '/'.join(['repos', self.user, self.repo, 'labels', urllib.parse.quote(old_name)]),
            {'new_name': new_name, 'color': color, 'description': description}
        )

    def delete_label(self, name):
        """Delete a label."""

        self._delete('/'.join(['repos', self.user, self.repo, 'labels', urllib.parse.quote(name)]))


# Label handling
class LabelEdit(namedtuple('LabelEdit', ['old', 'new', 'color', 'description', 'modified'])):
    """Label Edit tuple."""


class GhLabelSync:
    """GitHub label sync class."""

    def __init__(self, config, git, delete=False, debug=False):
        """Initialize."""

        self.debug = debug
        self.delete = delete
        self._parse_colors(config)
        self._parse_labels(config)
        self.git = git

    def _validate_str(self, name):
        """Validate name."""

        if not isinstance(name, str):
            raise TypeError("Key value is not of type 'str', type '{}' received instead".format(type(name)))

    def _validate_color(self, color):
        """Validate color."""

        self._validate_str(color)

        if RE_VALID_COLOR.match(color) is None:
            raise ValueError('{} is not a valid color'.format(color))

    def _get_repo(self):
        """Get the desired repository."""

        target = None
        for repo in self.user.get_repos():
            if repo.name == self.repo_name:
                target = repo
                break
        return target

    def _parse_labels(self, config):
        """Parse labels."""

        self.labels = {}
        seen = set()
        for name, value in config.get('labels', {}).items():
            self._validate_str(name)
            value['color'] = self._resolve_color(value['color'])
            if 'renamed' in value:
                self._validate_str(value['renamed'])
            if 'description' in value and not isinstance(value['description'], str):
                raise ValueError("Description for '{}' should be of type str".format(name))
            if name.lower() in seen:
                raise ValueError("The name '{}' is already present in the label list".format(name))
            seen.add(name.lower())
            self.labels[name] = value

        self.ignores = set()
        for name in config.get('ignores', []):
            self._validate_str(name)
            self.ignores.add(name.lower())

    def _resolve_color(self, color):
        """Parse color."""

        if RE_VALID_COLOR.match(color) is None:
            color = self.colors[color]
        return color

    def _parse_colors(self, config):
        """Get colors."""

        self.colors = {}
        for name, color in config.get('colors', {}).items():
            self._validate_color(color)
            self._validate_str(name)
            if name in self.colors:
                raise ValueError("The name '{}' is already present in the color list".format(name))
            self.colors[name] = color[1:]

    def _find_label(self, label, label_color, label_description):
        """Find label."""

        edit = None
        for name, value in self.labels.items():
            old_name = value.get('renamed', name)

            if label.lower() != old_name.lower():
                continue

            new_name = name
            color = value['color']
            description = value.get('description', '')
            modified = False

            # Editing an existing label
            if (
                label.lower() == old_name.lower() and
                (label_color.lower() != color.lower() or label_description != description)
            ):
                modified = True
            edit = LabelEdit(old_name, new_name, color, description, modified=modified)
            break

        return edit

    def sync(self):
        """Sync labels."""

        updated = set()
        for label in self.git.get_labels():
            edit = self._find_label(label['name'], label['color'], label['description'])
            if edit is not None and edit.modified:
                print('    Updating {}: #{} "{}"'.format(edit.new, edit.color, edit.description))
                if not self.debug:
                    self.git.edit_label(edit.old, edit.new, edit.color, edit.description)
                updated.add(edit.old)
                updated.add(edit.new)
            else:
                if edit is None and self.delete and label['name'].lower() not in self.ignores:
                    print('    Deleting {}: #{} "{}"'.format(label['name'], label['color'], label['description']))
                    if not self.debug:
                        self.git.delete_label(label['name'])
                else:
                    print('    Skipping {}: #{} "{}"'.format(label['name'], label['color'], label['description']))
                updated.add(label['name'])
        for name, value in self.labels.items():
            color = value['color']
            description = value.get('description', '')

            if name not in updated:
                print('    Creating {}: #{} "{}"'.format(name, color, description))
                if not self.debug:
                    self.git.create_label(name, color, description)


def main():
    """Main."""

    dbg = os.getenv("INPUT_DEBUG", 'disable')
    if dbg == 'enable':
        debug = True
    elif dbg == 'disable':
        debug = False
    else:
        raise ValueError('Unknown value for debug: {}'.format(dbg))

    # Parse mode
    mode = os.getenv("INPUT_MODE", 'normal')
    if mode == 'delete':
        delete = True
    elif mode == 'normal':
        delete = False
    else:
        raise ValueError('Unknown mode: {}'.format(mode))

    # Get the user's name and repository so we can access the labels for the repository
    repository =  os.getenv("GITHUB_REPOSITORY")
    if repository and '/' in repository:
        user, repo = repository.split('/')
    else:
        raise ValueError('Could not acquire user name and repository name')

    # Acquire access token
    token = os.getenv("INPUT_TOKEN", '')
    if not token:
        raise ValueError('No token provided')

    # Parse label file
    labels = os.getenv("INPUT_FILE", '.github/labels.json')
    print('Reading labels from {}'.format(labels))
    with codecs.open(labels, 'r', encoding='utf-8') as f:
        config = yaml.load(f.read(), Loader=Loader)

    # Sync the labels
    git = Api(token, user, repo)
    GhLabelSync(config, git, delete, debug).sync()
    return 0


if __name__ == "__main__":
    sys.exit(main())
