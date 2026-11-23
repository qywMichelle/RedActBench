"""Apply a tested overlay only to explicitly configured benchmark CLI children."""
import sys


def configure(config_path='/data/project/RedActBench/performance-overlay-config.json'):
    # Most venv users do not even read configuration or import the overlay.
    if len(sys.argv) < 2 or sys.argv[1] not in {'run', 'check-run', 'export'}:
        return
    if not sys.argv[0].endswith('/redact_bench.py'):
        return
    import json
    import os
    from pathlib import Path
    import time
    try:
        config = json.loads(Path(config_path).read_text())
        target = str(Path(sys.argv[0]).resolve())
        if not config.get('enabled') or target not in config['entrypoints']:
            return
        if sys.getprofile() is not None:
            return
    except (OSError, ValueError, KeyError):
        return

    def activate(frame, event, arg):
        if event != 'call' or frame.f_code.co_name != 'main' or frame.f_code.co_filename != target:
            return
        sys.setprofile(None)
        record = {'pid': os.getpid(), 'command': sys.argv[1], 'entrypoint': target, 'time': time.time()}
        try:
            import importlib.util
            import hashlib
            source = Path(config['source'])
            sha = hashlib.sha256(source.read_bytes()).hexdigest()
            if sha != config['source_sha256']:
                raise ValueError('overlay source SHA mismatch')
            spec = importlib.util.spec_from_file_location('redact_performance_overlay', source)
            overlay = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(overlay)
            overlay.install(sys.modules['__main__'], config['cache_directory'])
            record.update(status='active', version=overlay.VERSION, source_sha256=sha)
            if config.get('extra'):
                extra = config['extra']
                source = Path(extra['source'])
                extra_sha = hashlib.sha256(source.read_bytes()).hexdigest()
                if extra_sha != extra['sha256']:
                    raise ValueError('throughput overlay source SHA mismatch')
                extra_config = json.loads(Path(extra['config']).read_text())
                spec = importlib.util.spec_from_file_location('redact_throughput_overlay', source)
                throughput = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(throughput)
                throughput.install(sys.modules['__main__'], extra_config)
                record.update(throughput_enabled=bool(extra_config.get('enabled')),
                    throughput_source_sha256=extra_sha)
        except Exception as exc:
            # An unavailable overlay must not stop the original evaluator.
            record.update(status='baseline_fallback', error_type=type(exc).__name__)
        try:
            with Path(config['activation_log']).open('a') as stream:
                stream.write(json.dumps(record, separators=(',', ':')) + '\n')
        except OSError:
            pass

    sys.setprofile(activate)
