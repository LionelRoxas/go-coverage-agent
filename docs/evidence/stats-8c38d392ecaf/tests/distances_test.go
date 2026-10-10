package stats

import (
	"errors"
	"math"
	"testing"
)

func distancesFloatClose(got, want float64) bool {
	const eps = 1e-9
	if math.IsNaN(got) && math.IsNaN(want) {
		return true
	}
	return math.Abs(got-want) <= eps
}

func TestValidateData_Cases(t *testing.T) {
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
			if tc.wantErr != nil {
				if !errors.Is(err, tc.wantErr) {
					t.Fatalf("expected error %v, got %v", tc.wantErr, err)
				}
				return
			}
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
		})
	}
}

func TestChebyshevDistance_Cases(t *testing.T) {
	cases := []struct {
		name     string
		x, y     Float64Data
		wantDist float64
		wantErr  error
	}{
		{"normal", Float64Data{1, -2, 3}, Float64Data{4, -5, 0}, 3, nil},
		{"empty input", Float64Data{}, Float64Data{1}, math.NaN(), EmptyInputErr},
		{"size mismatch", Float64Data{1, 2}, Float64Data{1}, math.NaN(), SizeErr},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := ChebyshevDistance(tc.x, tc.y)
			if tc.wantErr != nil {
				if !errors.Is(err, tc.wantErr) {
					t.Fatalf("expected error %v, got %v", tc.wantErr, err)
				}
				if !math.IsNaN(got) {
					t.Fatalf("expected NaN distance on error, got %v", got)
				}
				return
			}
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			if !distancesFloatClose(got, tc.wantDist) {
				t.Fatalf("distance mismatch: got %v, want %v", got, tc.wantDist)
			}
		})
	}
}

func TestManhattanDistance_Cases(t *testing.T) {
	cases := []struct {
		name     string
		x, y     Float64Data
		wantDist float64
		wantErr  error
	}{
		{"normal", Float64Data{1, -2, 3}, Float64Data{4, -5, 0}, 9, nil},
		{"empty input", Float64Data{}, Float64Data{1}, math.NaN(), EmptyInputErr},
		{"size mismatch", Float64Data{1, 2}, Float64Data{1}, math.NaN(), SizeErr},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := ManhattanDistance(tc.x, tc.y)
			if tc.wantErr != nil {
				if !errors.Is(err, tc.wantErr) {
					t.Fatalf("expected error %v, got %v", tc.wantErr, err)
				}
				if !math.IsNaN(got) {
					t.Fatalf("expected NaN distance on error, got %v", got)
				}
				return
			}
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			if !distancesFloatClose(got, tc.wantDist) {
				t.Fatalf("distance mismatch: got %v, want %v", got, tc.wantDist)
			}
		})
	}
}

func TestEuclideanDistance_Cases(t *testing.T) {
	cases := []struct {
		name     string
		x, y     Float64Data
		wantDist float64
		wantErr  error
	}{
		{"normal", Float64Data{1, -2, 3}, Float64Data{4, -5, 0}, math.Sqrt(27), nil},
		{"empty input", Float64Data{}, Float64Data{1}, math.NaN(), EmptyInputErr},
		{"size mismatch", Float64Data{1, 2}, Float64Data{1}, math.NaN(), SizeErr},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := EuclideanDistance(tc.x, tc.y)
			if tc.wantErr != nil {
				if !errors.Is(err, tc.wantErr) {
					t.Fatalf("expected error %v, got %v", tc.wantErr, err)
				}
				if !math.IsNaN(got) {
					t.Fatalf("expected NaN distance on error, got %v", got)
				}
				return
			}
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			if !distancesFloatClose(got, tc.wantDist) {
				t.Fatalf("distance mismatch: got %v, want %v", got, tc.wantDist)
			}
		})
	}
}

func TestMinkowskiDistance_Cases(t *testing.T) {
	cases := []struct {
		name     string
		x, y     Float64Data
		lambda   float64
		wantDist float64
		wantErr  error
	}{
		{"lambda 1 equals Manhattan", Float64Data{1, -2, 3}, Float64Data{4, -5, 0}, 1, 9, nil},
		{"lambda 2 equals Euclidean", Float64Data{1, -2, 3}, Float64Data{4, -5, 0}, 2, math.Sqrt(27), nil},
		{"overflow returns InfValue", Float64Data{1e154}, Float64Data{-1e154}, 2, math.NaN(), InfValue},
		{"empty input", Float64Data{}, Float64Data{1}, 2, math.NaN(), EmptyInputErr},
		{"size mismatch", Float64Data{1, 2}, Float64Data{1}, 2, math.NaN(), SizeErr},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := MinkowskiDistance(tc.x, tc.y, tc.lambda)
			if tc.wantErr != nil {
				if !errors.Is(err, tc.wantErr) {
					t.Fatalf("expected error %v, got %v", tc.wantErr, err)
				}
				if !math.IsNaN(got) {
					t.Fatalf("expected NaN distance on error, got %v", got)
				}
				return
			}
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			if !distancesFloatClose(got, tc.wantDist) {
				t.Fatalf("distance mismatch: got %v, want %v", got, tc.wantDist)
			}
		})
	}
}
