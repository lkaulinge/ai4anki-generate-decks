# app.py

from flask import Flask, request, send_file, jsonify
import genanki
import requests
import os
import tempfile
import random
import logging

app = Flask(__name__)

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Pre-generated unique 32-bit model_id
MODEL_ID = 1607392319  # Replace with your own unique model_id

# Define Anki model with centered content
MY_MODEL = genanki.Model(
    model_id=MODEL_ID,  # Fixed unique 32-bit integer
    name='AI4ANKI',
    fields=[
        {'name': 'Target Language'},
        {'name': 'Origin Language'},
        {'name': 'Sound'},
    ],
    templates=[
        {
            'name': 'Card 1',
            'qfmt': '{{Target Language}}<br/><br/>{{Sound}}',
            'afmt': '{{FrontSide}}<hr/>{{Origin Language}}',
        },
    ],
    css='''
    .card {
        font-family: arial;
        font-size: 30px;
        color: black;
        background-color: white;
        text-align: center;
    }
    '''
)

# Define Anki deck
def create_deck(deck_name):
    deck_id = random.randrange(1 << 30, 1 << 31)  # Generate a unique 32-bit deck_id
    return genanki.Deck(
        deck_id,
        deck_name
    )

# Define a subclass of genanki.Note for stable GUIDs (optional)
class StableNote(genanki.Note):
    @property
    def guid(self):
        # Assuming 'Target Language' and 'Origin Language' uniquely identify the note
        return genanki.guid_for(self.fields[0], self.fields[1])

# Route to create Anki deck
@app.route('/create-deck', methods=['POST'])
def create_deck_route():
    try:
        data = request.get_json()
        if not data:
            logger.error('No JSON payload received.')
            return jsonify({'error': 'Invalid JSON payload.'}), 400

        # Extract top-level fields
        target_language_deck = data.get('target_language')
        origin_language_deck = data.get('origin_language')
        sentences = data.get('sentences')

        # Validate top-level fields
        if not target_language_deck or not isinstance(target_language_deck, str):
            logger.error('Invalid or missing "target_language" field.')
            return jsonify({'error': 'Invalid or missing "target_language" field.'}), 400

        if not origin_language_deck or not isinstance(origin_language_deck, str):
            logger.error('Invalid or missing "origin_language" field.')
            return jsonify({'error': 'Invalid or missing "origin_language" field.'}), 400

        if not sentences or not isinstance(sentences, list):
            logger.error('Invalid or missing "sentences" field.')
            return jsonify({'error': 'Invalid or missing "sentences" field.'}), 400

        deck_name = f'AI4ANKI-{target_language_deck}'
        deck = create_deck(deck_name)

        # Initialize a list to collect media file paths
        media_files = []

        # Temporary directory to store audio files
        with tempfile.TemporaryDirectory() as tmpdirname:
            for idx, sentence in enumerate(sentences):
                target_language = sentence.get('target_language')
                origin_language = sentence.get('origin_language')
                audio_url = sentence.get('audio_url')

                if not target_language or not origin_language:
                    logger.warning(f"Skipping sentence {idx + 1} due to missing fields.")
                    continue

                # Fetch audio
                if audio_url:
                    try:
                        response = requests.get(audio_url, timeout=10)
                        response.raise_for_status()
                        audio_content = response.content
                    except requests.RequestException as e:
                        logger.error(f"Error fetching audio for sentence {idx + 1}: {e}")
                        continue

                    # Generate unique filename
                    audio_filename = os.path.basename(audio_url)
                    audio_path = os.path.join(tmpdirname, audio_filename)

                    # Save audio to temp directory
                    with open(audio_path, 'wb') as f:
                        f.write(audio_content)

                    # Add audio path to media_files list
                    media_files.append(audio_path)
                
                if audio_url:
                    fields=[target_language, origin_language, f"[sound:{audio_filename}]"]
                else:
                    fields=[target_language, origin_language, ""]

                # Create note with stable GUID
                note = StableNote(
                    model=MY_MODEL,
                    fields=fields
                )
                deck.add_note(note)
                if audio_url:
                    logger.info(f"Added Note {idx + 1} with audio")
                else:
                    logger.info(f"Added Note {idx + 1} without audio")
            if not deck.notes:
                logger.error('No valid sentences to add to the deck.')
                return jsonify({'error': 'No valid sentences to add to the deck.'}), 400

            # Create the package after all notes and media files have been added
            package = genanki.Package(deck, media_files=media_files)  # Assign the collected media files

            # Generate .apkg file within the same temporary directory
            with tempfile.NamedTemporaryFile(delete=False, suffix='.apkg') as tmpfile:
                package.write_to_file(tmpfile.name)
                tmpfile_path = tmpfile.name

            logger.info(f"Deck '{deck_name}' created successfully with {len(deck.notes)} notes and {len(media_files)} media files.")

        return send_file(
            tmpfile_path,
            as_attachment=True,
            download_name=f"{deck_name}.apkg",
            mimetype='application/vnd.anki.apkg'
        )

    except Exception as e:
        logger.exception("An unexpected error occurred during deck creation.")
        return jsonify({'error': 'An unexpected error occurred.', 'message': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8579, debug=True)