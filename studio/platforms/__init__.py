"""Clients des API officielles de publication. Aucun contournement : uniquement les flux OAuth
et endpoints documentés par chaque plateforme. Les jetons sont lus depuis l'environnement."""
import os


class MissingCredentials(RuntimeError):
    pass


def need(*names):
    vals = [os.environ.get(n) for n in names]
    missing = [n for n, v in zip(names, vals) if not v]
    if missing:
        raise MissingCredentials("identifiants manquants : " + ", ".join(missing))
    return vals
