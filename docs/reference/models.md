# Metadata models

These immutable records are returned by project objects and result loaders. Analysis code normally reads their attributes rather than constructing them directly. Python field names use `snake_case`; the [export specification](../specifications/export-v2.md) documents the original JSON field names.

## Project and registration

::: neuroqp.Manifest

::: neuroqp.ExportMetadata

::: neuroqp.ProjectMetadata

::: neuroqp.Atlas

::: neuroqp.AtlasRegistration

::: neuroqp.BrainRegion

::: neuroqp.DetailTransform

## Classification and matching

::: neuroqp.ClassifierMetadata

::: neuroqp.TrainingSummary

::: neuroqp.TrainingSample

::: neuroqp.ClassificationResultInfo

::: neuroqp.MatchResultInfo

::: neuroqp.SliceExclusion

::: neuroqp.SharedDetectionSource

::: neuroqp.IndependentDetectionSource

## Validation and limits

::: neuroqp.ExportLimits

::: neuroqp.ValidationReport

::: neuroqp.ValidationIssue
