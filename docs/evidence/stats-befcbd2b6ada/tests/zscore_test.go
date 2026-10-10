package stats

import (
	"errors"
	"math"
	"testing"
)

func zscoreSlicesApproxEqual(t *testing.T, got, want []float64, tol float64) {
	if len(got) != len(want) {
		t.Fatalf("length mismatch: got %d, want %d", len(got), len(want))
	}
	for i := range got {
		if math.IsNaN(got[i]) && math.IsNaN(want[i]) {
			continue
		}
		if math.Abs(got[i]-want[i]) > tol {
			t.Fatalf("at index %d: got %v, want %v (tol %v)", i, got[i], want[i], tol)
		}
	}
}

func TestZScore(t *testing.T) {
	cases := []struct {
		name    string
		input   Float64Data
		want    []float64
		wantErr error
	}{
		{"EmptyInput", Float64Data{}, nil, ErrEmptyInput},
		{"ZeroStdDev", Float64Data{5, 5, 5}, nil, ErrZero},
		{"Basic", Float64Data{1, 2, 3, 4, 5}, []float64{-1.2649110640673518, -0.6324555320336759, 0, 0.6324555320336759, 1.2649110640673518}, nil},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := ZScore(tc.input)
			if !errors.Is(err, tc.wantErr) {
				t.Fatalf("unexpected error: got %v, want %v", err, tc.wantErr)
			}
			if tc.wantErr == nil {
				zscoreSlicesApproxEqual(t, got, tc.want, 1e-9)
			}
		})
	}
}

func TestFloat64Data_ZScore(t *testing.T) {
	cases := []struct {
		name    string
		input   Float64Data
		wantErr error
	}{
		{"EmptyInput", Float64Data{}, ErrEmptyInput},
		{"ZeroStdDev", Float64Data{5, 5, 5}, ErrZero},
		{"Basic", Float64Data{1, 2, 3, 4, 5}, nil},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := tc.input.ZScore()
			if !errors.Is(err, tc.wantErr) {
				t.Fatalf("unexpected error: got %v, want %v", err, tc.wantErr)
			}
			if tc.wantErr == nil {
				want, _ := ZScore(tc.input)
				zscoreSlicesApproxEqual(t, got, want, 1e-9)
			}
		})
	}
}
