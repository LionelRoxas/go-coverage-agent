package stats

import (
	"errors"
	"math"
	"testing"
)

func coefficientOfVariationApproxEqual(t *testing.T, got, want float64) {
	const eps = 1e-9
	if math.IsNaN(got) && math.IsNaN(want) {
		return
	}
	if math.Abs(got-want) > eps {
		t.Fatalf("got %v, want %v", got, want)
	}
}

func TestCoefficientOfVariation(t *testing.T) {
	cases := []struct {
		name    string
		input   Float64Data
		want    float64
		wantErr error
	}{
		{"EmptyInput", Float64Data{}, math.NaN(), ErrEmptyInput},
		{"MeanZero", Float64Data{-1, 1}, math.NaN(), ErrZero},
		{"NormalCase", Float64Data{1, 2, 3, 4, 5}, 0.5270462766947299, nil},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := CoefficientOfVariation(tc.input)
			if !errors.Is(err, tc.wantErr) {
				t.Fatalf("unexpected error: %v, want %v", err, tc.wantErr)
			}
			if tc.wantErr == nil {
				coefficientOfVariationApproxEqual(t, got, tc.want)
			} else {
				if !math.IsNaN(got) {
					t.Fatalf("expected NaN result on error, got %v", got)
				}
			}
		})
	}
}

func TestFloat64Data_CoefficientOfVariation(t *testing.T) {
	cases := []struct {
		name    string
		input   Float64Data
		want    float64
		wantErr error
	}{
		{"EmptyInput", Float64Data{}, math.NaN(), ErrEmptyInput},
		{"MeanZero", Float64Data{-1, 1}, math.NaN(), ErrZero},
		{"NormalCase", Float64Data{1, 2, 3, 4, 5}, 0.5270462766947299, nil},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := tc.input.CoefficientOfVariation()
			if !errors.Is(err, tc.wantErr) {
				t.Fatalf("unexpected error: %v, want %v", err, tc.wantErr)
			}
			if tc.wantErr == nil {
				coefficientOfVariationApproxEqual(t, got, tc.want)
			} else {
				if !math.IsNaN(got) {
					t.Fatalf("expected NaN result on error, got %v", got)
				}
			}
		})
	}
}
