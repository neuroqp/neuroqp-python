"""Reader-bound public API façade."""

from ._classification import Classification, ClassificationModule, Match
from ._objects import (
    Animal,
    FileArtifact,
    Image,
    Registration,
    Slice,
    SliceRegistration,
    Staining,
)
from ._project import ProjectExport
from ._results import (
    ClassificationResult,
    ClassificationResults,
    MatchResult,
    MatchResults,
)

__all__ = [
    "Animal",
    "Classification",
    "ClassificationModule",
    "ClassificationResult",
    "ClassificationResults",
    "FileArtifact",
    "Image",
    "Match",
    "MatchResult",
    "MatchResults",
    "ProjectExport",
    "Registration",
    "Slice",
    "SliceRegistration",
    "Staining",
]
