package stats

import (
	"math"
	"testing"
)

func coefficientOfVariationApproxEqual(a, b float64) bool {
	const eps = 1e-9
	if math.IsNaN(a) && math.IsNaN(b) {
		return true
	}
	return math.Abs(a-b) <= eps
}

func TestCoefficientOfVariation(t *testing.T) {
	cases := []struct {
		name    string
		input   Float64Data
		want    float64
		wantErr error
	}{
		{"EmptyInput", Float64Data{}, math.NaN(), ErrEmptyInput},
		{"ZeroMean", Float64Data{-1, 1}, math.NaN(), ErrZero},
		{"Normal", Float64Data{1, 2, 3, 4, 5}, 0.5270462766947299, nil},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := CoefficientOfVariation(tc.input)
			if tc.wantErr != nil {
				if err != tc.wantErr {
					t.Fatalf("expected error %v, got %v", tc.wantErr, err)
				}
				if !math.IsNaN(got) {
					t.Fatalf("expected NaN result, got %v", got)
				}
				return
			}
			if err != nil {
				t.Fatalf("unexpected error %v", err)
			}
			if !coefficientOfVariationApproxEqual(got, tc.want) {
				t.Fatalf("got %v, want %v", got, tc.want)
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
		{"ZeroMean", Float64Data{-1, 1}, math.NaN(), ErrZero},
		{"Normal", Float64Data{1, 2, 3, 4, 5}, 0.5270462766947299, nil},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := tc.input.CoefficientOfVariation()
			if tc.wantErr != nil {
				if err != tc.wantErr {
					t.Fatalf("expected error %v, got %v", tc.wantErr, err)
				}
				if !math.IsNaN(got) {
					t.Fatalf("expected NaN result, got %v", got)
				}
				return
			}
			if err != nil {
				t.Fatalf("unexpected error %v", err)
			}
			if !coefficientOfVariationApproxEqual(got, tc.want) {
				t.Fatalf("got %v, want %v", got, tc.want)
			}
		})
	}
}
