package stats

import (
	"errors"
	"math"
	"testing"
)

func TestMedianAbsoluteDeviationPopulation(t *testing.T) {
	cases := []struct {
		name    string
		input   Float64Data
		want    float64
		wantErr error
	}{
		{"empty", Float64Data{}, math.NaN(), EmptyInputErr},
		{"odd", Float64Data{1, 2, 3, 4, 5}, 1, nil},
		{"even", Float64Data{1, 2, 3, 4}, 1, nil},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := MedianAbsoluteDeviationPopulation(tc.input)
			if !errors.Is(err, tc.wantErr) {
				t.Fatalf("expected error %v, got %v", tc.wantErr, err)
			}
			if tc.wantErr == nil {
				if math.IsNaN(tc.want) {
					if !math.IsNaN(got) {
						t.Fatalf("expected NaN, got %v", got)
					}
				} else {
					if math.Abs(got-tc.want) > 1e-9 {
						t.Fatalf("expected %v, got %v", tc.want, got)
					}
				}
			}
		})
	}
}

func TestMedianAbsoluteDeviation(t *testing.T) {
	cases := []struct {
		name    string
		input   Float64Data
		want    float64
		wantErr error
	}{
		{"empty", Float64Data{}, math.NaN(), EmptyInputErr},
		{"odd", Float64Data{1, 2, 3, 4, 5}, 1, nil},
		{"even", Float64Data{1, 2, 3, 4}, 1, nil},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := MedianAbsoluteDeviation(tc.input)
			if !errors.Is(err, tc.wantErr) {
				t.Fatalf("expected error %v, got %v", tc.wantErr, err)
			}
			if tc.wantErr == nil {
				if math.IsNaN(tc.want) {
					if !math.IsNaN(got) {
						t.Fatalf("expected NaN, got %v", got)
					}
				} else {
					if math.Abs(got-tc.want) > 1e-9 {
						t.Fatalf("expected %v, got %v", tc.want, got)
					}
				}
			}
		})
	}
}

func TestStandardDeviationSample(t *testing.T) {
	cases := []struct {
		name    string
		input   Float64Data
		want    float64
		wantErr error
	}{
		{"empty", Float64Data{}, math.NaN(), EmptyInputErr},
		{"basic", Float64Data{2, 4, 4, 4, 5, 5, 7, 9}, 2.138089935299395, nil},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := StandardDeviationSample(tc.input)
			if !errors.Is(err, tc.wantErr) {
				t.Fatalf("expected error %v, got %v", tc.wantErr, err)
			}
			if tc.wantErr == nil {
				if math.IsNaN(tc.want) {
					if !math.IsNaN(got) {
						t.Fatalf("expected NaN, got %v", got)
					}
				} else {
					if math.Abs(got-tc.want) > 1e-9 {
						t.Fatalf("expected %v, got %v", tc.want, got)
					}
				}
			}
		})
	}
}
