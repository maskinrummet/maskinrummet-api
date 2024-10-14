import os
from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from flask_bcrypt import Bcrypt

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})
bcrypt = Bcrypt(app)

app.config['SQLALCHEMY_DATABASE_URI'] = os.environ["MYSQLCONNSTR_Maskinrummet"]
app.config["SQLALCHEMY_POOL_RECYCLE"] = 299
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

class Dataset(db.Model):
    __tablename__ = "datasets"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50))
    password = db.Column(db.String(4096))
    is_open = db.Column(db.Boolean, default=False)
    use_value = db.Column(db.Boolean, default=False)
    value_name = db.Column(db.String(50), default=None)

class Sentence(db.Model):
    __tablename__ = "sentences"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    text = db.Column(db.String(250))
    value = db.Column(db.Integer, default=0)
    dataset_id = db.Column(db.Integer, primary_key=True)

@app.route("/datasets", methods=["GET"])
def get_datasets():
    datasets = Dataset.query.all()
    dataset_names = [{"id": dataset.id, "name": dataset.name, "is_open": dataset.is_open} for dataset in datasets]
    return jsonify(dataset_names)

@app.route("/datasets/<int:id>", methods=["GET"])
def get_dataset(id):
    dataset = Dataset.query.get(id)
    if dataset:
        sentences = Sentence.query.filter_by(dataset_id=id).all()
        sentences_serialised = [{"id": s.id, "text": s.text, "value": s.value} for s in sentences]
        return jsonify({"id": dataset.id, "name": dataset.name, "is_open": dataset.is_open, "use_value": dataset.use_value, "value_name": dataset.value_name, "sentences": sentences_serialised})
    else:
        return jsonify({"error": "Dataset not found"}), 404

@app.route("/datasets/<int:id>/verify", methods=["POST"])
def verify_dataset_password(id):
    password = request.json.get("password")
    dataset = Dataset.query.get(id)
    if dataset:
        if bcrypt.check_password_hash(dataset.password, password):
            return jsonify({"message": "Verified"})
    return jsonify({"error": "Incorrect password"}), 401

@app.route("/datasets/<int:id>/add", methods=["POST"])
def add_sentence_to_dataset(id):
    dataset = Dataset.query.get(id)
    if dataset:
        if dataset.is_open:
            new_text = request.json.get("new_text")
            if not new_text:
                return jsonify({"error": "No sentence provided"}), 400
            if len(new_text) > 250:
                return jsonify({"error": "Sentence too long"}), 400
            new_value = request.json.get("new_value")
            if new_value and not new_value.removeprefix('-').isdigit():
                return jsonify({"error": "Invalid value"}), 400
            new_sentence = Sentence(text = new_text, value = int(new_value) if new_value else 0, dataset_id = id)
            db.session.add(new_sentence)
            db.session.commit()
            return jsonify({"message": "Sentence added successfully"})
        else:
            return jsonify({"error": "Dataset is not open for adding sentences"}), 403
    else:
        return jsonify({"error": "Dataset not found"}), 404

@app.route("/datasets/new", methods=["POST"])
def add_dataset():
    name = request.json.get("name")
    password = request.json.get("password")
    is_open = request.json.get("is_open")
    use_value = request.json.get("use_value")
    value_name = request.json.get("value_name")
    sentences = request.json.get("sentences")
    if (not name) or (not password):
        return jsonify({"error": "Dataset must have name and password"}), 400
    if len(name) > 50:
        return jsonify({"error": "Dataset name must be less than 50 characters"}), 400
    if value_name and len(value_name) > 50:
        return jsonify({"error": "Value name must be less than 50 characters"}), 400
    for s in sentences:
        if not s["text"]:
            return jsonify({"error": "A dataset cannot contain an empty sentence"}), 400
        if len(s["text"]) > 250:
                return jsonify({"error": "Sentence(s) too long"}), 400
        if not str(s["value"]).removeprefix('-').isdigit():
                return jsonify({"error": "Invalid value(s)"}), 400
    new_dataset = Dataset(name=name, password=bcrypt.generate_password_hash(password=password).decode('utf-8'), is_open=True if is_open else False, use_value=True if use_value else False)
    db.session.add(new_dataset)
    db.session.flush() 
    db.session.add_all([Sentence(text = s["text"], value = int(s["value"]) if s["value"] else 0, dataset_id = new_dataset.id) for s in sentences])
    db.session.commit()
    return jsonify({"message": "Dataset added successfully", "id": new_dataset.id}), 201

@app.route("/datasets/<int:id>/delete", methods=["POST"])
def remove_dataset(id):
    password = request.json.get("password")
    dataset = Dataset.query.get(id)
    if not dataset:
        return jsonify({"error": "Dataset not found"}), 404
    if bcrypt.check_password_hash(dataset.password, password):
        db.session.delete(dataset)
        Sentence.query.filter_by(dataset_id=id).delete()
        db.session.commit()
        return jsonify({"message": "Dataset deleted successfully"})
    else:
        return jsonify({"error": "Incorrect password"}), 401

@app.route("/datasets/<int:id>/edit", methods=["POST"])
def edit_dataset(id):
    password = request.json.get("password")
    new_name = request.json.get("new_name")
    new_is_open = request.json.get("new_is_open")
    new_use_value = request.json.get("new_use_value")
    new_value_name = request.json.get("new_value_name")
    new_sentences = request.json.get("new_sentences")
    edited_sentences = request.json.get("edited_sentences")
    sentences_to_remove = request.json.get("sentences_to_remove")
    dataset = Dataset.query.get(id)
    if not dataset:
        return jsonify({"error": "Dataset not found"}), 404
    if bcrypt.check_password_hash(dataset.password, password):
        if new_name:
            if len(new_name) > 50:
                return jsonify({"error": "Dataset name must be less than 50 characters"}), 400
            dataset.name = new_name
        dataset.is_open = True if new_is_open else False
        dataset.use_value = True if new_use_value else False
        if new_value_name:
            if len(new_value_name) > 50:
                return jsonify({"error": "Value name must be less than 50 characters"}), 400
            dataset.value_name = new_value_name
        for s in new_sentences:
            if not s["text"]:
                return jsonify({"error": "A dataset cannot contain an empty sentence"}), 400
            if len(s["text"]) > 250:
                    return jsonify({"error": "Sentence(s) too long"}), 400
            if not str(s["value"]).removeprefix('-').isdigit():
                    return jsonify({"error": "Invalid value(s)"}), 400
        for s in sentences_to_remove:
            if not str(s).isdigit():
                return jsonify({"error": "Invalid sentences to remove"}), 400
        for s in edited_sentences:
            if not s["text"]:
                return jsonify({"error": "A dataset cannot contain an empty sentence"}), 400
            if len(s["text"]) > 250:
                    return jsonify({"error": "Sentence(s) too long"}), 400
            if not str(s["value"]).removeprefix('-').isdigit():
                    return jsonify({"error": "Invalid value(s)"}), 400
        for s in edited_sentences:
            sentence = db.session.query(Sentence).filter_by(id=s["id"]).first()
            if sentence:
                sentence.text = s["text"]
                sentence.value = int(s["value"]) if s["value"] else 0
            else:
                db.session.add(Sentence(id=s["id"], text=s["text"], value=int(s["value"]) if s["value"] else 0, dataset_id=id))
        db.session.query(Sentence).filter(Sentence.id.in_([int(s) for s in sentences_to_remove])).delete(synchronize_session=False)
        db.session.add_all([Sentence(text = s["text"], value = int(s["value"]) if s["value"] else 0, dataset_id = id) for s in new_sentences])
        db.session.commit()
        return jsonify({"message": "Dataset updated successfully"})
    else:
        return jsonify({"error": "Incorrect password"}), 401   
    
# unlikely to be useful
""" @app.route("/datasets/<int:id>/open", methods=["POST"])
def open_dataset(id):
    dataset = Dataset.query.get(id)
    if dataset:
        password = request.json.get("password")
        if bcrypt.check_password_hash(dataset.password, password):
            dataset.is_open = True
            db.session.commit()
            return jsonify({"message": "Dataset opened successfully"})
    return jsonify({"error": "Dataset not found or incorrect password"}), 404 """