package stats

import (
	"errors"
	"math"
	"testing"
)

func TestInterp(t *testing.T) {
	const eps = 1e-12
	cases := []struct {
		name           string
		x, xp, fp      Float64Data
		want           []float64
		wantErr        error
		wantNaNIndices []int
	}{
		{
			name:    "EmptyX",
			x:       Float64Data{},
			xp:      Float64Data{0, 1},
			fp:      Float64Data{0, 1},
			wantErr: ErrEmptyInput,
		},
		{
			name:    "EmptyXP",
			x:       Float64Data{0},
			xp:      Float64Data{},
			fp:      Float64Data{},
			wantErr: ErrEmptyInput,
		},
		{
			name:    "SizeMismatch",
			x:       Float64Data{0},
			xp:      Float64Data{0, 1},
			fp:      Float64Data{0},
			wantErr: ErrSize,
		},
		{
			name:    "NonIncreasingXP",
			x:       Float64Data{0},
			xp:      Float64Data{0, 0, 1},
			fp:      Float64Data{0, 0, 1},
			wantErr: ErrBounds,
		},
		{
			name:    "NaNInXP",
			x:       Float64Data{0},
			xp:      Float64Data{math.NaN(), 1},
			fp:      Float64Data{0, 1},
			wantErr: ErrBounds,
		},
		{
			name:           "NaNInX",
			x:              Float64Data{math.NaN()},
			xp:             Float64Data{0, 1},
			fp:             Float64Data{10, 20},
			want:           []float64{math.NaN()},
			wantNaNIndices: []int{0},
		},
		{
			name: "BelowFirstKnot",
			x:    Float64Data{-5},
			xp:   Float64Data{0, 10},
			fp:   Float64Data{100, 200},
			want: []float64{100},
		},
		{
			name: "AboveLastKnot",
			x:    Float64Data{15},
			xp:   Float64Data{0, 10},
			fp:   Float64Data{100, 200},
			want: []float64{200},
		},
		{
			name: "ExactKnot",
			x:    Float64Data{10},
			xp:   Float64Data{0, 10, 20},
			fp:   Float64Data{0, 5, 10},
			want: []float64{5},
		},
		{
			name: "LinearInterpolation",
			x:    Float64Data{5},
			xp:   Float64Data{0, 10},
			fp:   Float64Data{0, 10},
			want: []float64{5},
		},
		{
			name: "OverflowDifference",
			x:    Float64Data{0},
			xp:   Float64Data{-math.MaxFloat64, math.MaxFloat64},
			fp:   Float64Data{0, 1},
			want: []float64{0.5},
		},
	}

	for _, tc := range cases {
		tc := tc // capture range variable
		t.Run(tc.name, func(t *testing.T) {
			got, err := Interp(tc.x, tc.xp, tc.fp)
			if tc.wantErr != nil {
				if err == nil || !errors.Is(err, tc.wantErr) {
					t.Fatalf("expected error %v, got %v", tc.wantErr, err)
				}
				return
			}
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			if len(got) != len(tc.want) {
				t.Fatalf("result length %d, want %d", len(got), len(tc.want))
			}
			for i := range got {
				// check NaN expectation first
				isNaNIdx := false
				for _, idx := range tc.wantNaNIndices {
					if i == idx {
						isNaNIdx = true
						break
					}
				}
				if isNaNIdx {
					if !math.IsNaN(got[i]) {
						t.Fatalf("index %d: expected NaN, got %v", i, got[i])
					}
					continue
				}
				wantVal := tc.want[i]
				if math.IsNaN(wantVal) {
					if !math.IsNaN(got[i]) {
						t.Fatalf("index %d: expected NaN, got %v", i, got[i])
					}
					continue
				}
				if math.IsInf(wantVal, 0) {
					if !math.IsInf(got[i], 0) || math.Signbit(got[i]) != math.Signbit(wantVal) {
						t.Fatalf("index %d: expected %v, got %v", i, wantVal, got[i])
					}
					continue
				}
				if math.Abs(got[i]-wantVal) > eps {
					t.Fatalf("index %d: expected %v, got %v (diff %v)", i, wantVal, got[i], math.Abs(got[i]-wantVal))
				}
			}
		})
	}
}
