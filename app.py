#!/usr/bin/env python3
"""
Flask web application for esxtop batch data analysis.
Provides a web interface to upload CSV files and run analysis.
"""

import ast
import os
import subprocess
import tempfile
import shutil
import time
from pathlib import Path
from flask import Flask, render_template, request, jsonify, send_file, redirect, url_for
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024  # 500MB max upload
app.config['OUTPUT_FOLDER'] = os.environ.get('ESXTOP_OUTPUT_FOLDER', '/tmp/esxtop_output')
# Uploads land in a per-analysis directory under OUTPUT_FOLDER, and are removed
# with it. 0 disables pruning and lets the output directory grow unbounded.
app.config['OUTPUT_RETENTION_HOURS'] = float(
    os.environ.get('ESXTOP_OUTPUT_RETENTION_HOURS', '24')
)

ALLOWED_EXTENSIONS = {'csv'}


def read_version():
    """
    Read __version__ from the package without importing it.

    src/esxtop_visualizer/__init__.py is the single source of truth (see
    [tool.setuptools.dynamic] in pyproject.toml). Parsing the AST rather than
    importing keeps matplotlib out of the web app's import path, and matches
    how setuptools resolves the same value at build time.
    """
    init_py = Path(__file__).parent / 'src' / 'esxtop_visualizer' / '__init__.py'
    try:
        tree = ast.parse(init_py.read_text(encoding='utf-8'))
    except (OSError, SyntaxError):
        return 'unknown'

    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id == '__version__':
                if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                    return node.value.value
    return 'unknown'


VERSION = read_version()


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def ensure_dirs():
    """Ensure the output directory exists."""
    os.makedirs(app.config['OUTPUT_FOLDER'], exist_ok=True)


def prune_old_outputs():
    """
    Delete analysis directories older than OUTPUT_RETENTION_HOURS.

    Without this the output volume grows by one directory per upload and is
    never reclaimed. Errors are swallowed: another worker may be pruning the
    same directory concurrently, and a failed cleanup must not fail the upload.
    """
    retention_hours = app.config['OUTPUT_RETENTION_HOURS']
    if retention_hours <= 0:
        return

    cutoff = time.time() - retention_hours * 3600
    output_folder = app.config['OUTPUT_FOLDER']

    try:
        entries = os.listdir(output_folder)
    except OSError:
        return

    for name in entries:
        path = os.path.join(output_folder, name)
        try:
            if os.path.isdir(path) and os.path.getmtime(path) < cutoff:
                shutil.rmtree(path, ignore_errors=True)
        except OSError:
            continue


def run_analysis(csv_path, analysis_type, output_dir):
    """
    Run esxtop analysis script and capture output.

    Args:
        csv_path: Path to the uploaded CSV file
        analysis_type: 'describe', 'describe-pdisk', or 'both'
        output_dir: Directory for output files

    Returns:
        dict with 'output' (text), 'success' (bool), 'files' (list of generated files)
    """
    results = {
        'output': '',
        'success': True,
        'files': [],
        'errors': []
    }

    # Change to output directory for generated files
    original_dir = os.getcwd()
    os.chdir(output_dir)

    try:
        scripts_dir = Path(__file__).parent / 'scripts'

        if analysis_type in ('describe', 'both'):
            # Run describe analysis (non-interactive mode)
            result = run_describe_script(csv_path, scripts_dir, 'describe_extop_web.sh')
            results['output'] += f"\n{'='*60}\nVMDK ANALYSIS (Virtual Disk)\n{'='*60}\n"
            results['output'] += result['output']
            if not result['success']:
                results['errors'].append(result.get('error', 'Unknown error in describe'))

        if analysis_type in ('describe-pdisk', 'both'):
            # Run physical disk analysis
            result = run_describe_script(csv_path, scripts_dir, 'describe_physical_disk.sh')
            results['output'] += f"\n{'='*60}\nPHYSICAL DISK ANALYSIS\n{'='*60}\n"
            results['output'] += result['output']
            if not result['success']:
                results['errors'].append(result.get('error', 'Unknown error in describe-pdisk'))

        # Collect generated files
        for f in os.listdir(output_dir):
            if f.endswith(('.png', '.data', '_col_ids')):
                results['files'].append(f)

        results['success'] = len(results['errors']) == 0

    except Exception as e:
        results['success'] = False
        results['errors'].append(str(e))
    finally:
        os.chdir(original_dir)

    return results


def run_describe_script(csv_path, scripts_dir, script_name):
    """Run a describe script and capture output."""
    script_path = scripts_dir / script_name

    # For the web version, we need a non-interactive script
    if script_name == 'describe_extop_web.sh':
        # Use the web-specific script that skips interactive prompts
        script_path = scripts_dir / 'describe_extop_web.sh'
        if not script_path.exists():
            script_path = scripts_dir / 'describe_extop.sh'

    try:
        # Run with 'yes' piped to handle any interactive prompts
        process = subprocess.Popen(
            ['bash', str(script_path), str(csv_path)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.PIPE,
            text=True,
            env={**os.environ, 'TERM': 'dumb'}  # Disable color codes
        )
        stdout, stderr = process.communicate(input='y\n', timeout=300)  # 5 min timeout

        # Strip ANSI color codes
        import re
        ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
        stdout = ansi_escape.sub('', stdout)

        return {
            'output': stdout,
            'success': process.returncode == 0,
            'error': stderr if process.returncode != 0 else None
        }
    except subprocess.TimeoutExpired:
        process.kill()
        return {
            'output': '',
            'success': False,
            'error': 'Analysis timed out after 5 minutes'
        }
    except Exception as e:
        return {
            'output': '',
            'success': False,
            'error': str(e)
        }


@app.route('/')
def index():
    """Render the main upload page."""
    return render_template('index.html', version=VERSION)


@app.route('/upload', methods=['POST'])
def upload_file():
    """Handle CSV file upload and run analysis."""
    ensure_dirs()
    prune_old_outputs()

    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400

    if not allowed_file(file.filename):
        return jsonify({'error': 'Only CSV files are allowed'}), 400

    analysis_type = request.form.get('analysis_type', 'both')

    # Create unique output directory for this analysis
    output_dir = tempfile.mkdtemp(dir=app.config['OUTPUT_FOLDER'])

    # Save uploaded file
    filename = secure_filename(file.filename)
    csv_path = os.path.join(output_dir, filename)
    file.save(csv_path)

    # Run analysis
    results = run_analysis(csv_path, analysis_type, output_dir)

    # Store output_dir in session or return it for file downloads
    results['output_dir'] = os.path.basename(output_dir)
    results['filename'] = filename

    return jsonify(results)


@app.route('/download/<output_dir>/<filename>')
def download_file(output_dir, filename):
    """Download a generated file."""
    # Security: ensure we're only accessing files in output folder
    safe_dir = secure_filename(output_dir)
    safe_file = secure_filename(filename)
    file_path = os.path.join(app.config['OUTPUT_FOLDER'], safe_dir, safe_file)

    if os.path.exists(file_path):
        return send_file(file_path, as_attachment=True)
    return jsonify({'error': 'File not found'}), 404


@app.route('/health')
def health():
    """Health check endpoint."""
    return jsonify({'status': 'healthy'})


# Run at import so the directory exists under gunicorn, which never executes
# the __main__ block below.
ensure_dirs()


if __name__ == '__main__':
    # Development entry point only. The container runs gunicorn (see Dockerfile).
    app.run(host='0.0.0.0', port=5000, debug=False)
