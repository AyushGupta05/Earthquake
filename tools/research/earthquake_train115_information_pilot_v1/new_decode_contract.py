"""Public callback failure: received native scalar count, never payload or authority."""


class ObservedDecodeFailure(ValueError):
    def __init__(self, observed_samples):
        if type(observed_samples) is not int or not 0 <= observed_samples <= 2**63-1:
            raise RuntimeError('observed_accounting_invalid')
        super().__init__('decode_unknown')
        self.observed_samples = observed_samples
