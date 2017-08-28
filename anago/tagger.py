import os
from collections import defaultdict

from keras.optimizers import Adam

from anago.data.preprocess import WordPreprocessor
from anago.data.reader import load_word_embeddings
from anago.models import SeqLabeling


class Tagger(object):

    def __init__(self, config, weights, tokenizer=str.split):
        self.config = config
        self._tokenizer = tokenizer
        self.p = WordPreprocessor.load(os.path.join(self.config.save_path, 'preprocessor.pkl'))

        self.config.char_vocab_size = len(self.p.vocab_char)
        self.config.vocab_size = len(self.p.vocab_word)

        self.model = SeqLabeling(self.config, ntags=len(self.p.vocab_tag))
        self.model.compile(loss=self.model.loss,
                           optimizer=Adam(lr=self.config.learning_rate),
                           )
        self.model.load(filepath=os.path.join(self.config.save_path, weights))

    def predict(self, words):
        sequence_lengths = [len(words)]
        X = self.p.transform([words])
        pred = self.model.predict(X, sequence_lengths)
        pred = self.p.inverse_transform(pred[0])
        return pred

    def tag(self, sent):
        """Tags a sentence named entities.

        Args:
            sent: a sentence

        Return:
            labels_pred: list of (word, tag) for a sentence

        Example:
            >>> sent = 'President Obama is speaking at the White House.'
            >>> print(self.tag(sent))
            [('President', 'O'), ('Obama', 'PERSON'), ('is', 'O'),
             ('speaking', 'O'), ('at', 'O'), ('the', 'O'),
             ('White', 'LOCATION'), ('House', 'LOCATION'), ('.', 'O')]
        """
        assert isinstance(sent, str)

        words = self._tokenizer(sent)
        pred = self.predict(words)
        pred = [t.split('-')[-1] for t in pred]  # remove prefix: e.g. B-Person -> Person

        return list(zip(words, pred))

    def get_entities(self, sent):
        """Gets entities from a sentence.

        Args:
            sent: a sentence

        Return:
            labels_pred: dict of entities for a sentence

        Example:
            sent = 'President Obama is speaking at the White House.'
            result = {'Person': ['Obama'], 'LOCATION': ['White House']}
        """
        assert isinstance(sent, str)

        words = self._tokenizer(sent)
        pred = self.predict(words)
        entities = self.get_chunks(words, pred)

        return entities

    def get_chunks(self, words, tags):
        """
        Args:
            words: sequence of word
            tags: sequence of labels

        Returns:
            dict of entities for a sequence

        Example:
            words = ['President', 'Obama', 'is', 'speaking', 'at', 'the', 'White', 'House', '.']
            tags = ['O', 'B-Person', 'O', 'O', 'O', 'O', 'B-Location', 'I-Location', 'O']
            result = {'Person': ['Obama'], 'LOCATION': ['White House']}
        """
        chunks = []
        chunk_type, chunk_start = None, None
        for i, tok in enumerate(tags):
            # End of a chunk 1
            if tok == 'O' and chunk_type is not None:
                # Add a chunk.
                chunk = (chunk_type, chunk_start, i)
                chunks.append(chunk)
                chunk_type, chunk_start = None, None

            # End of a chunk + start of a chunk!
            elif tok != 'O':
                tok_chunk_class, tok_chunk_type = tok.split('-')
                if chunk_type is None:
                    chunk_type, chunk_start = tok_chunk_type, i
                elif tok_chunk_type != chunk_type or tok_chunk_class == "B":
                    chunk = (chunk_type, chunk_start, i)
                    chunks.append(chunk)
                    chunk_type, chunk_start = tok_chunk_type, i
            else:
                pass
        # end condition
        if chunk_type is not None:
            chunk = (chunk_type, chunk_start, len(tags))
            chunks.append(chunk)

        res = defaultdict(list)
        for chunk_type, chunk_start, chunk_end in chunks:
            res[chunk_type].append(' '.join(words[chunk_start: chunk_end]))  # todo delimiter changeable

        return res
