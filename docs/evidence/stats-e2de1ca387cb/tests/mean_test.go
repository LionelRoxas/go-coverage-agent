package stats

import (
	"errors"
	"math"
	"testing"
)

func TestGeometricMean_ErrorsAndNormal(t *testing.T) {
	cases := []struct {
		name    string
		input   []float64
		want    float64
		wantErr error
		wantNaN bool
	}{
		{"empty", []float64{}, math.NaN(), EmptyInputErr, true},
		{"negative", []float64{-1, 2}, math.NaN(), NegativeErr, true},
		{"zero", []float64{0, 2}, math.NaN(), ZeroErr, true},
		{"normal", []float64{1, 2, 4}, 2.0, nil, false},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := GeometricMean(Float64Data(tc.input))
			if !errors.Is(err, tc.wantErr) {
				t.Fatalf("expected error %v, got %v", tc.wantErr, err)
			}
			if tc.wantNaN {
				if !math.IsNaN(got) {
					t.Fatalf("expected NaN, got %v", got)
				}
			} else {
				if math.Abs(got-tc.want) > 1e-9 {
					t.Fatalf("expected %v, got %v", tc.want, got)
				}
			}
		})
	}
}

func TestHarmonicMean_ErrorsAndNormal(t *testing.T) {
	cases := []struct {
		name    string
		input   []float64
		want    float64
		wantErr error
		wantNaN bool
	}{
		{"empty", []float64{}, math.NaN(), EmptyInputErr, true},
		{"negative", []float64{-1, 2}, math.NaN(), NegativeErr, true},
		{"zero", []float64{0, 2}, math.NaN(), ZeroErr, true},
		{"normal", []float64{1, 2, 4}, 3.0 / (1 + 0.5 + 0.25), nil, false},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := HarmonicMean(Float64Data(tc.input))
			if !errors.Is(err, tc.wantErr) {
				t.Fatalf("expected error %v, got %v", tc.wantErr, err)
			}
			if tc.wantNaN {
				if !math.IsNaN(got) {
					t.Fatalf("expected NaN, got %v", got)
				}
			} else {
				if math.Abs(got-tc.want) > 1e-9 {
					t.Fatalf("expected %v, got %v", tc.want, got)
				}
			}
		})
	}
}

func TestMean_EmptyInput(t *testing.T) {
	got, err := Mean(Float64Data{})
	if !errors.Is(err, EmptyInputErr) {
		t.Fatalf("expected EmptyInputErr, got %v", err)
	}
	if !math.IsNaN(got) {
		t.Fatalf("expected NaN result, got %v", got)
	}
}
