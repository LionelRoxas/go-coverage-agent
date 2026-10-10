package stats

import (
	"errors"
	"math"
	"testing"
)

func meanApproxEqual(got, want float64) bool {
	const eps = 1e-9
	if math.IsNaN(got) && math.IsNaN(want) {
		return true
	}
	return math.Abs(got-want) <= eps
}

func TestGeometricMean(t *testing.T) {
	cases := []struct {
		name    string
		input   Float64Data
		want    float64
		wantErr error
	}{
		{"empty", Float64Data{}, math.NaN(), EmptyInputErr},
		{"negative", Float64Data{-1, 2}, math.NaN(), NegativeErr},
		{"zero", Float64Data{0, 2}, math.NaN(), ZeroErr},
		{"normal", Float64Data{1, 3, 9}, 3, nil},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := GeometricMean(tc.input)
			if !errors.Is(err, tc.wantErr) {
				t.Fatalf("expected error %v, got %v", tc.wantErr, err)
			}
			if tc.wantErr == nil {
				if !meanApproxEqual(got, tc.want) {
					t.Errorf("expected %v, got %v", tc.want, got)
				}
			} else {
				if !math.IsNaN(got) {
					t.Errorf("expected NaN result, got %v", got)
				}
			}
		})
	}
}

func TestHarmonicMean(t *testing.T) {
	cases := []struct {
		name    string
		input   Float64Data
		want    float64
		wantErr error
	}{
		{"empty", Float64Data{}, math.NaN(), EmptyInputErr},
		{"negative", Float64Data{-1, 2}, math.NaN(), NegativeErr},
		{"zero", Float64Data{0, 2}, math.NaN(), ZeroErr},
		{"normal", Float64Data{1, 2, 4}, 1.7142857142857142, nil},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := HarmonicMean(tc.input)
			if !errors.Is(err, tc.wantErr) {
				t.Fatalf("expected error %v, got %v", tc.wantErr, err)
			}
			if tc.wantErr == nil {
				if !meanApproxEqual(got, tc.want) {
					t.Errorf("expected %v, got %v", tc.want, got)
				}
			} else {
				if !math.IsNaN(got) {
					t.Errorf("expected NaN result, got %v", got)
				}
			}
		})
	}
}
