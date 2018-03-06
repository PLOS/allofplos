import warnings

from .update import main

if __name__ == "__main__":
    warnings.simplefilter('always', DeprecationWarning)
    warnings.warn("This update method is deprecated. use 'python -m allofplos.update'",
                  DeprecationWarning,
                  stacklevel=2)
    main()
