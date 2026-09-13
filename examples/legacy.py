
# examples/legacy.py
#
# Demo file for CodeDrift.
# Contains a mix of outdated patterns (should be flagged) and one
# intentional pattern (should be skipped by the AI advisor).


# --- Should be flagged: len(x) == 0 instead of truthiness check ---
def has_no_items(items):
    if len(items) == 0:
        return True
    return False


# --- Should be flagged: legacy % string formatting ---
def format_greeting(name, score):
    return "Hello %s, your score is %d points." % (name, score)


# --- Should be flagged: type() equality instead of isinstance() ---
def describe(value):
    if type(value) == int:
        return "This is an integer."
    return "This is something else."


# --- Intentional: strict type() check kept on purpose ---
# bool is a subclass of int in Python, so isinstance(value, int) would
# incorrectly accept True/False here. We need the exact type only.
def is_pure_integer(value):
    if type(value) == int:
        return True
    return False


# --- Should be flagged: .has_key() (removed in Python 3) ---
def legacy_lookup(config):
    if config.has_key("timeout"):
        return config["timeout"]
    return None