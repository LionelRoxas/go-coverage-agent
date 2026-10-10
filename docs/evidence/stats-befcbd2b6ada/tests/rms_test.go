package stats

import (
	"errors"
	"math"
	"testing"
)

func rmsApproxEqual(got, want float64) bool {
	const eps = 1e-9
	if math.IsNaN(got) && math.IsNaN(want) {
		return true
	}
	return math.Abs(got-want) <= eps
}

func TestRMS(t *testing.T) {
	cases := []struct {
		name    string
		input   Float64Data
		want    float64
		wantErr error
	}{
		{"empty", Float64Data{}, math.NaN(), ErrEmptyInput},
		{"single", Float64Data{3}, 3, nil},
		{"multiple", Float64Data{1, -2, 3}, math.Sqrt((1*1 + 4 + 9) / 3.0), nil},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := RMS(tc.input)
			if !errors.Is(err, tc.wantErr) {
				t.Fatalf("unexpected error: %v, want %v", err, tc.wantErr)
			}
			if tc.wantErr == nil {
				if !rmsApproxEqual(got, tc.want) {
					t.Errorf("RMS(%v) = %v, want %v", tc.input, got, tc.want)
				}
			} else {
				if !math.IsNaN(got) {
					t.Errorf("expected NaN result for error case, got %v", got)
				}
			}
		})
	}
}

func TestFloat64Data_RMS(t *testing.T) {
	cases := []struct {
		name    string
		input   Float64Data
		want    float64
		wantErr error
	}{
		{"empty", Float64Data{}, math.NaN(), ErrEmptyInput},
		{"two", Float64Data{4, 0}, math.Sqrt((16 + 0) / 2.0), nil},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := tc.input.RMS()
			if !errors.Is(err, tc.wantErr) {
				t.Fatalf("unexpected error: %v, want %v", err, tc.wantErr)
			}
			if tc.wantErr == nil {
				if !rmsApproxEqual(got, tc.want) {
					t.Errorf("Float64Data.RMS(%v) = %v, want %v", tc.input, got, tc.want)
				}
			} else {
				if !math.IsNaN(got) {
					t.Errorf("expected NaN result for error case, got %v", got)
				}
			}
		})
	}
}
