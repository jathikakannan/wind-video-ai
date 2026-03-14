from jiwer import wer

def calculate_wer(reference, prediction):
    """
    Calculate Word Error Rate (WER) between
    the reference text and predicted transcript.

    WER = (Substitutions + Insertions + Deletions) / Total words
    """

    # Handle empty inputs safely
    if not reference or not prediction:
        return 0.0

    try:
        error_rate = wer(reference, prediction)
        return round(error_rate, 4)
    except Exception as e:
        print("WER calculation error:", e)
        return 0.0