"""
The time indexing of the flow results written to the output database
"""

from enum import StrEnum, unique

ANNUAL_TIME_SLICE = 'annual'


@unique
class FlowsIndexing(StrEnum):
    DEFAULT = 'default'
    ANNUAL = 'annual'
    TIME_SLICED = 'time_sliced'

    @classmethod
    def parse(cls, raw: object) -> 'FlowsIndexing':
        try:
            return cls(str(raw).strip().lower())
        except ValueError as err:
            raise ValueError(
                f'Invalid flows_indexing: "{raw}".  Valid choices are: {[m.value for m in cls]}'
            ) from err
