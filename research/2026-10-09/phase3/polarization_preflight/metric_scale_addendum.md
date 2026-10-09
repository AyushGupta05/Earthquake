# Protocol v2 metric-scale clarification

Recorded 2026-10-09T21:43:03.917917+00:00, before any real waveform extraction or fitting. Parent explicitly approved this clarification. The original protocol v2 file/hash is unchanged: `a9b12a88be3a46e96d0f3f208f64b7728d1a17bb132e146887694e40288a448b`.

The geometry targets are fitted in their specified log spaces. The primary5% geometry MAE gate is measured in original kilometres for hypocentral distance or depth. Transformed-space errors are separately reported. Inverse transforms are exact (`10**prediction` for distance, `expm1(prediction)` for depth). Physically invalid predictions are counted and reported, never clipped; nonfinite predictions make the corresponding fit incomplete/failed. The frozen all-duration/all-subset gate selects the same geometry target across comparisons, with no per-horizon target switching.

This resolves a previously unspecified reporting scale. No target values, fitted predictions or errors informed it.
