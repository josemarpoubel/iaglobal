    try:
        from flask import Flask, jsonify, request
    except ImportError:
        import logging
        logging.warning(
            "[DEPENDENCY] flask nao encontrado. "
            "Adicione ao requirements.txt e execute 'pip install -r requirements.txt'"
        )
        flask = None  # type: ignore[assignment]

app = Flask(__name__)

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok'})

if __name__ == '__main__':
    app.run(debug=True)