package stats

import (
	"errors"
	"math"
	"testing"
)

func distancesApproxEqual(a, b float64) bool {
	const eps = 1e-9
	if math.IsNaN(a) && math.IsNaN(b) {
		return true
	}
	return math.Abs(a-b) <= eps
}

func TestValidateData(t *testing.T) {
	cases := []struct {
		name    string
		x, y    Float64Data
		wantErr error
	}{
		{"empty input", Float64Data{}, Float64Data{1, 2}, EmptyInputErr},
		{"empty second", Float64Data{1, 2}, Float64Data{}, EmptyInputErr},
		{"size mismatch", Float64Data{1, 2}, Float64Data{1}, SizeErr},
		{"valid", Float64Data{1, 2}, Float64Data{3, 4}, nil},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			err := validateData(tc.x, tc.y)
			if !errors.Is(err, tc.wantErr) {
				t.Fatalf("expected error %v, got %v", tc.wantErr, err)
			}
		})
	}
}

func TestChebyshevDistance(t *testing.T) {
	cases := []struct {
		name     string
		x, y     Float64Data
		wantDist float64
		wantErr  error
	}{
		{"empty input", Float64Data{}, Float64Data{1}, 0, EmptyInputErr},
		{"size mismatch", Float64Data{1, 2}, Float64Data{1}, 0, SizeErr},
		{"normal case", Float64Data{1, 2, 3}, Float64Data{4, 0, 3}, 3, nil},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := ChebyshevDistance(tc.x, tc.y)
			if !errors.Is(err, tc.wantErr) {
				t.Fatalf("expected error %v, got %v", tc.wantErr, err)
			}
			if tc.wantErr == nil && !distancesApproxEqual(got, tc.wantDist) {
				t.Fatalf("expected distance %v, got %v", tc.wantDist, got)
			}
		})
	}
}

func TestMinkowskiDistance(t *testing.T) {
	cases := []struct {
		name     string
		x, y     Float64Data
		lambda   float64
		wantDist float64
		wantErr  error
	}{
		{"empty input", Float64Data{}, Float64Data{1}, 2, 0, EmptyInputErr},
		{"size mismatch", Float64Data{1, 2}, Float64Data{1}, 2, 0, SizeErr},
		{"lambda=2 matches Euclidean", Float64Data{0, 3}, Float64Data{4, 0}, 2, 5, nil},
		{"inf overflow", Float64Data{1, 2}, Float64Data{3, 4}, 0.0001, math.NaN(), InfValue},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := MinkowskiDistance(tc.x, tc.y, tc.lambda)
			if !errors.Is(err, tc.wantErr) {
				t.Fatalf("expected error %v, got %v", tc.wantErr, err)
			}
			if tc.wantErr == nil {
				if !distancesApproxEqual(got, tc.wantDist) {
					t.Fatalf("expected distance %v, got %v", tc.wantDist, got)
				}
			}
		})
	}
}

func TestEuclideanDistance(t *testing.T) {
	cases := []struct {
		name     string
		x, y     Float64Data
		wantDist float64
		wantErr  error
	}{
		{"empty input", Float64Data{}, Float64Data{1}, 0, EmptyInputErr},
		{"size mismatch", Float64Data{1, 2}, Float64Data{1}, 0, SizeErr},
		{"normal case", Float64Data{0, 3}, Float64Data{4, 0}, 5, nil},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := EuclideanDistance(tc.x, tc.y)
			if !errors.Is(err, tc.wantErr) {
				t.Fatalf("expected error %v, got %v", tc.wantErr, err)
			}
			if tc.wantErr == nil && !distancesApproxEqual(got, tc.wantDist) {
				t.Fatalf("expected distance %v, got %v", tc.wantDist, got)
			}
		})
	}
}

func TestManhattanDistance(t *testing.T) {
	cases := []struct {
		name     string
		x, y     Float64Data
		wantDist float64
		wantErr  error
	}{
		{"empty input", Float64Data{}, Float64Data{1}, 0, EmptyInputErr},
		{"size mismatch", Float64Data{1, 2}, Float64Data{1}, 0, SizeErr},
		{"normal case", Float64Data{1, 2}, Float64Data{4, 0}, 5, nil},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := ManhattanDistance(tc.x, tc.y)
			if !errors.Is(err, tc.wantErr) {
				t.Fatalf("expected error %v, got %v", tc.wantErr, err)
			}
			if tc.wantErr == nil && !distancesApproxEqual(got, tc.wantDist) {
				t.Fatalf("expected distance %v, got %v", tc.wantDist, got)
			}
		})
	}
}
