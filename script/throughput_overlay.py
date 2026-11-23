"""Route future children through the equivalent bridge; wait on owned run locks."""
from contextlib import contextmanager
import json
from pathlib import Path
import time
import urllib.error
import urllib.request
import zipfile


class RoutingOpener:
    def __init__(self, original, source, target, enabled=True, redirect_legacy=True):
        self.original, self.source, self.target = original, source, target
        self.enabled = enabled
        self.redirect_legacy = redirect_legacy

    def __getattr__(self, name):
        return getattr(self.original, name)

    def open(self, request, *args, **kwargs):
        if isinstance(request, urllib.request.Request) and request.full_url in {self.source, self.target}:
            if request.full_url == self.source and not self.redirect_legacy:
                return self.original.open(request, *args, **kwargs)
            destination = self.target if self.enabled else self.source
            request = urllib.request.Request(destination, data=request.data,
                headers=dict(request.header_items()), method=request.get_method())
        try:
            return self.original.open(request, *args, **kwargs)
        except urllib.error.URLError as exc:
            if (isinstance(request, urllib.request.Request) and request.full_url == self.target and
                    isinstance(exc.reason, ConnectionRefusedError)):
                # No request was accepted. A dead auxiliary bridge cannot stop
                # the original model; keep the same bytes on the legacy bridge.
                fallback = urllib.request.Request(self.source, data=request.data,
                    headers=dict(request.header_items()), method=request.get_method())
                return self.original.open(fallback, *args, **kwargs)
            raise


def install(bench, config):
    source = config['legacy_endpoint']
    target = config['accelerated_endpoint']
    owned = {str(Path(p).resolve()) for p in config['owned_runs']}
    original_build = bench.urllib.request.build_opener
    original_lock = bench.recovery.writer_lock
    original_export = bench.export_run
    original_run = bench.run

    def build(*args, **kwargs):
        return RoutingOpener(original_build(*args, **kwargs), source, target, config.get('enabled', False),
                             config.get('redirect_legacy', False))

    @contextmanager
    def writer_lock(output):
        if str(Path(output).resolve()) not in owned:
            with original_lock(output):
                yield
            return
        # Keep the original exclusive writer. A natural main worker reaching an
        # in-progress auxiliary batch waits; no overlapping writes or failures.
        while True:
            context = original_lock(output)
            try:
                context.__enter__()
            except ValueError as exc:
                if str(exc) != 'Another process is writing this run directory':
                    raise
                time.sleep(.5)
            else:
                break
        try:
            yield
        except BaseException as exc:
            if not context.__exit__(type(exc), exc, exc.__traceback__):
                raise
        else:
            context.__exit__(None, None, None)

    bench.urllib.request.build_opener = build
    bench.recovery.writer_lock = writer_lock

    def run(args):
        if str(args.output.resolve()) not in owned:
            return original_run(args)
        args.output.mkdir(parents=True, exist_ok=True)
        with writer_lock(args.output):
            saved_path = args.output / 'run_config.json'
            if not args.resume and saved_path.is_file():
                saved = bench.load(saved_path)
                _, _, requested = bench.select(args)
                same_cases = [entry['case'] for entry in requested] == saved['cases']
                same_options = all(getattr(args, name) is None or getattr(args, name) == saved[name]
                    for name in bench.recovery.BOUND_OPTIONS)
                requested_url = bench.endpoint(args.url, args.protocol or saved['protocol']) if args.url else saved['url']
                same_route = requested_url == saved['url'] or {requested_url, saved['url']} <= {source, target}
                if same_cases and same_options and same_route:
                    args.resume, args.url = True, None
            previous_lock = bench.recovery.writer_lock
            @contextmanager
            def held(output):
                if output.resolve() != args.output.resolve():
                    raise ValueError('Nested writer attempted a different run')
                yield
            bench.recovery.writer_lock = held
            try:
                return original_run(args)
            finally:
                bench.recovery.writer_lock = previous_lock
    bench.run = run

    def export(args):
        expected = config.get('owned_exports', {}).get(str(args.run.resolve()))
        if expected is None or str(args.output.resolve()) != expected:
            return original_export(args)
        with writer_lock(args.run):
            if args.output.exists():
                report = bench.check_run(args.run)
                with zipfile.ZipFile(args.output) as archive:
                    hashes = json.loads(archive.read('trace-integrity.json'))
                    saved = json.loads(archive.read('replay-verification.json'))
                if saved != report:
                    raise ValueError('Concurrent export replay report differs')
                for relative, sha in hashes.items():
                    path = args.run / relative
                    if (Path(relative).is_absolute() or '..' in Path(relative).parts or
                            path.is_symlink() or not path.resolve().is_relative_to(args.run.resolve()) or
                            not path.is_file() or bench.core.file_sha(path) != sha):
                        raise ValueError('Concurrent export content changed')
                print(json.dumps({'export': str(args.output), 'reused_concurrent_export': True, **report}), flush=True)
                return
            return original_export(args)
    bench.export_run = export
