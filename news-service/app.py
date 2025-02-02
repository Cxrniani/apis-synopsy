from flask import Flask, request, jsonify
from flask_cors import CORS
from db import init_db, store_news, get_news, get_all_news, update_news, delete_news

app = Flask(__name__)
CORS(app)

# Inicializa o banco de dados
init_db()

@app.route('/news', methods=['POST'])
def add_news():
    data = request.json
    title = data.get('title')
    subtitle = data.get('subtitle')
    image = data.get('image')
    content = data.get('content')

    if not title or not content:
        return jsonify({'error': 'Title and content are required'}), 400

    news_id = store_news(title, subtitle, image, content)
    return jsonify({'id': news_id}), 201

@app.route('/news/<int:id>', methods=['GET'])
def get_news_route(id):
    news = get_news(id)
    if news:
        return jsonify({
            'id': news[0],
            'title': news[1],
            'subtitle': news[2],
            'image': news[3],
            'content': news[4],
            'created_at': news[5]
        }), 200
    else:
        return jsonify({'error': 'News not found'}), 404

@app.route('/news', methods=['GET'])
def get_all_news_route():
    news_list = get_all_news()
    return jsonify([{
        'id': news[0],
        'title': news[1],
        'subtitle': news[2],
        'image': news[3],
        'content': news[4],
        'created_at': news[5]
    } for news in news_list]), 200

@app.route('/news/<int:id>', methods=['PUT'])
def update_news_route(id):
    data = request.json
    title = data.get('title')
    subtitle = data.get('subtitle')
    image = data.get('image')
    content = data.get('content')

    if update_news(id, title, subtitle, image, content):
        return jsonify({'message': 'News updated successfully'}), 200
    else:
        return jsonify({'error': 'News not found or no changes made'}), 404

@app.route('/news/<int:id>', methods=['DELETE'])
def delete_news_route(id):
    if delete_news(id):
        return jsonify({'message': 'News deleted successfully'}), 200
    else:
        return jsonify({'error': 'News not found'}), 404

if __name__ == '__main__':
    app.run(debug=True)