import requests
import base64
import hashlib
import yaml
import os

# set this to the SignalFX API key
SFX = os.environ['SFX']


def deterministic_id(key):
    h = hashlib.sha256(key).digest()
    b = base64.b64encode(h)
    return b[:11]


def replace_ids(ids, value):
    if isinstance(value, dict):
        if '$id' in value and 'kind' in value:
            id = ids.get(value['kind'], value['$id'])
            if not id:
                raise RuntimeError("{} not defined".format(value))
            return id
        return {k: replace_ids(ids, v) for k, v in value.iteritems()}
    elif isinstance(value, list):
        return [replace_ids(ids, v) for v in value]
    else:
        return value


def make_sfx_object(ids, kind, payload):
    headers={
        'content-type': 'application/json',
        'x-sf-token': SFX,
    }
    id = ids.get(kind, payload['name'])
    payload = replace_ids(ids, payload)
    if id:
        res = requests.put(
            'https://api.signalfx.com/v2/{}/{}'.format(kind, id),
            headers=headers,
            json=payload)
    else:
        res = requests.post(
            'https://api.signalfx.com/v2/{}'.format(kind),
            headers=headers,
            json=payload)
    try:
        res.raise_for_status()
    except Exception:
        print(res.text)
        raise
    obj = res.json()
    ids.set(kind, payload['name'], obj['id'])
    return obj


class IdManager(object):

    def __init__(self):
        self.data = {}
        if os.path.exists('ids.yml'):
            with open('ids.yml') as f:
                self.data = yaml.load(f)

    def _flush(self):
        with open('ids.yml', 'w') as f:
            yaml.safe_dump(self.data, f)

    def get(self, kind, name):
        return self.data.setdefault(kind, {}).get(name)

    def set(self, kind, name, id):
        existing = self.data.setdefault(kind, {}).get(name)
        if existing != id:
            self.data[kind][name] = id
            self._flush()


def main():
    ids = IdManager()

    with open('chartz.yml') as f:
        cfg = yaml.load(f)

    for name, chart in cfg['charts'].iteritems():
        chart['name'] = name
        obj = make_sfx_object(ids, 'chart', chart)
        print("chart {}: {}".format(name, obj['id']))

    for name, dg in cfg['dashboardgroups'].iteritems():
        dg['name'] = name
        obj = make_sfx_object(ids, 'dashboardgroup', dg)
        print("dashboardgroup {}: {}".format(name, obj['id']))

    for name, dg in cfg['dashboards'].iteritems():
        dg['name'] = name
        obj = make_sfx_object(ids, 'dashboard', dg)
        print("dashboard {}: {}".format(name, obj['id']))


main()
