#!/usr/bin/env python3
"""Fail before compilation if generated Xcode paths escape verified roots."""
import argparse
import json
from pathlib import Path


def require(value, message):
    if not value:
        raise ValueError(message)


def verify(stage, repo, settings):
    stage, repo = Path(stage).resolve(), Path(repo).resolve()
    require(stage.is_relative_to(repo), 'Stage outside checkout')
    project = json.loads((stage / 'project.yml').read_text())
    app = project['targets']['NativeAudioLifecycle']
    expected = [repo / 'experiments/audio-lifecycle/native/Host/NativeAudioHost.swift',
                repo / 'App/Server/LoopbackServer.swift', repo / 'App/Server/HTTPProtocol.swift']
    require(app['sources'][:3] == [str(p) for p in expected], 'Unexpected resolved source paths')
    require(app['sources'][3:] == ['NativeAudioIdentity.swift',
            {'path': 'Web', 'type': 'folder', 'buildPhase': 'resources'}], 'Unexpected staged resource paths')
    ui = repo / 'experiments/audio-lifecycle/native/UITests/NativeAudioLifecycleUITests.swift'
    require(project['targets']['NativeAudioLifecycleUITests']['sources'] == [str(ui)], 'Unexpected UI source')
    for path in expected + [ui, stage / 'NativeAudioIdentity.swift', stage / 'Info.plist']:
        require(path.is_file() and not path.is_symlink() and path.resolve().is_relative_to(repo), 'Missing/unsafe source/plist')
    require((stage / 'Web/native-manifest.json').is_file(), 'Missing attested Web resources')
    require(app['info']['path'] == 'Info.plist', 'Relocated Info.plist template')
    selected = [x['buildSettings'] for x in settings if x.get('target') == 'NativeAudioLifecycle']
    require(len(selected) == 1, 'Missing/duplicate main target settings')
    actual = selected[0]
    require(Path(actual['PROJECT_DIR']).resolve() == stage and Path(actual['SRCROOT']).resolve() == stage,
            'Generated project root differs from staged spec')
    plist = Path(actual['INFOPLIST_FILE'])
    if not plist.is_absolute():
        plist = stage / plist
    require(plist.resolve() == stage / 'Info.plist', 'Xcode resolves Info.plist outside stage')
    return {'verified': True, 'projectRoot': 'native-stage', 'sourceFiles': 4,
            'resourceRoot': 'native-stage/Web', 'relocatedProject': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--stage', type=Path, required=True)
    parser.add_argument('--repo', type=Path, required=True)
    parser.add_argument('--settings', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(verify(args.stage, args.repo, json.loads(args.settings.read_text())), indent=2))
