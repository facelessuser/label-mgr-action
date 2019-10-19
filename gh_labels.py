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

        self.url = 'https://api.github.com'
        self.token = token
        self.user = user
        self.repo = repo

    def _delete(self, command, timeout=60, expected=200, headers=None):
        """Send a DELETE REST command."""

        if timeout == 0:
            timeout = None

        if headers is None:
            headers = {}

        headers['Authorization'] = 'token {}'.format(self.token)

        try:
            resp = requests.delete(
                command,
                headers=headers,
                timeout=timeout
            )

            assert resp.status_code == expected

        except Exception:
            raise RuntimeError('DELETE command failed: {}'.format(command))

    def _patch(self, command, payload, timeout=60, expected=200, headers=None):
        """Send a PATCH REST command."""

        if timeout == 0:
            timeout = None

        if headers is None:
            headers = {}

        headers['Authorization'] = 'token {}'.format(self.token)

        if payload is not None:
            payload = json.dumps(payload)
            headers['content-type'] = 'application/json'

        try:
            resp = requests.patch(
                command,
                data=payload,
                headers=headers,
                timeout=timeout
            )

            assert resp.status_code == expected

        except Exception:
            raise RuntimeError('PATCH command failed: {}'.format(command))

    def _post(self, command, payload, timeout=60, expected=200, headers=None):
        """Send a POST REST command."""

        if timeout == 0:
            timeout = None

        if headers is None:
            headers = {}

        headers['Authorization'] = 'token {}'.format(self.token)

        if payload is not None:
            payload = json.dumps(payload)
            headers['content-type'] = 'application/json'

        try:
            resp = requests.post(
                command,
                data=payload,
                headers=headers,
                timeout=timeout
            )

            assert resp.status_code == expected

        except Exception:
            raise RuntimeError('POST command failed: {}'.format(command))

    def _get(self, command, payload=None, timeout=60, pages=False, expected=200, headers=None, text=False):
        """Send a GET REST request."""

        if timeout == 0:
            timeout = None

        if headers is None:
            headers = {}

        headers['Authorization'] = 'token {}'.format(self.token)

        data = None

        while command:
            try:
                resp = requests.get(
                    command,
                    params=payload,
                    headers=headers,
                    timeout=timeout
                )

                assert resp.status_code == expected

                command = resp.links.get('next', {}).get('url', '') if pages else ''
                data = json.loads(resp.text) if not text else resp.text
                if pages and not text:
                    for entry in data:
                        yield entry
                else:
                    yield data

            except Exception:
                raise RuntimeError('GET command failed: {}'.format(command))

    def get_contents(self, file, ref="master"):
        """Get contents."""

        return list(
            self._get(
                '/'.join([self.url, 'repos', self.user, self.repo, 'contents',  urllib.parse.quote(file)]),
                headers={'Accept': 'application/vnd.github.v3.raw'},
                payload={'ref': ref},
                text=True
            )
        )[0]

    def get_labels(self):
        """Get labels."""

        return list(
            self._get(
                '/'.join([self.url, 'repos', self.user, self.repo, 'labels']),
                pages=True,
                headers={'Accept': 'application/vnd.github.symmetra-preview+json'}
            )
        )

    def create_label(self, name, color, description):
        """Create label."""

        self._post(
            '/'.join([self.url, 'repos', self.user, self.repo, 'labels']),
            {'name': name, 'color': color, 'description': description},
            headers={'Accept': 'application/vnd.github.symmetra-preview+json'},
            expected=201
        )

    def edit_label(self, old_name, new_name, color, description):
        """Edit label."""

        self._patch(
            '/'.join([self.url, 'repos', self.user, self.repo, 'labels', urllib.parse.quote(old_name)]),
            {'new_name': new_name, 'color': color, 'description': description},
            headers={'Accept': 'application/vnd.github.symmetra-preview+json'}
        )

    def delete_label(self, name):
        """Delete a label."""

        self._delete(
            '/'.join([self.url, 'repos', self.user, self.repo, 'labels', urllib.parse.quote(name)]),
             headers={'Accept': 'application/vnd.github.symmetra-preview+json'},
             expected=204
        )


# Label handling
class LabelEdit(namedtuple('LabelEdit', ['old', 'new', 'color', 'description', 'modified'])):
    """Label Edit tuple."""


class GhLabelSync:
    """GitHub label sync class."""

    def __init__(self, config, git, delete=False, debug=False):
        """Initialize."""

        self.git = git
        self.debug = debug
        self.delete = delete
        config = self._get_config(config)
        self._parse_colors(config)
        self._parse_labels(config)

    def _get_config(self, config):
        """Get config."""

        print('Reading labels from {}'.format(config))
        return yaml.load(self.git.get_contents(config, ref=os.getenv("GITHUB_SHA")), Loader=Loader)

    def _validate_str(self, name):
        """Validate name."""

        if not isinstance(name, str):
            raise TypeError("Key value is not of type 'str', type '{}' received instead".format(type(name)))

    def _validate_color(self, color):
        """Validate color."""

        self._validate_str(color)

        if RE_VALID_COLOR.match(color) is None:
            raise ValueError('{} is not a valid color'.format(color))

    def _parse_labels(self, config):
        """Parse labels."""

        self.labels = []
        seen = set()
        for value in config.get('labels', {}):
            name = value['name']
            self._validate_str(name)
            value['color'] = self._resolve_color(value['color'])
            if 'renamed' in value:
                self._validate_str(value['renamed'])
            if 'description' in value and not isinstance(value['description'], str):
                raise ValueError("Description for '{}' should be of type str".format(name))
            if name.lower() in seen:
                raise ValueError("The name '{}' is already present in the label list".format(name))
            seen.add(name.lower())
            self.labels.append(value)

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
        for value in self.labels:
            name = value['name']
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
        for value in self.labels:
            name = value['name']
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

    # Get label file
    config = os.getenv("INPUT_FILE", '.github/labels.yml')

    # Sync the labels
    git = Api(token, user, repo)
    GhLabelSync(config, git, delete, debug).sync()
    return 0


if __name__ == "__main__":
    sys.exit(main())
