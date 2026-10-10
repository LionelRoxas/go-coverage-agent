package stats

import (
	"errors"
	"math"
	"testing"
)

func TestValidateData_Errors(t *testing.T) {
	cases := []struct {
		name    string
		x, y    Float64Data
		wantErr error
	}{
		{"empty first", Float64Data{}, Float64Data{1, 2}, EmptyInputErr},
		{"empty second", Float64Data{1, 2}, Float64Data{}, EmptyInputErr},
		{"size mismatch", Float64Data{1, 2}, Float64Data{1}, SizeErr},
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

func TestChebyshevDistance_NormalAndError(t *testing.T) {
	// Normal case
	x := Float64Data{1, -2, 3}
	y := Float64Data{4, -5, 0}
	got, err := ChebyshevDistance(x, y)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if got != 3 {
		t.Fatalf("expected distance 3, got %v", got)
	}
	// Error case: size mismatch
	_, err = ChebyshevDistance(Float64Data{1, 2}, Float64Data{1})
	if !errors.Is(err, SizeErr) {
		t.Fatalf("expected SizeErr, got %v", err)
	}
}

func TestEuclideanDistance_NormalAndError(t *testing.T) {
	x := Float64Data{1, -2, 3}
	y := Float64Data{4, -5, 0}
	got, err := EuclideanDistance(x, y)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	want := math.Sqrt(27)
	if math.Abs(got-want) > 1e-9 {
		t.Fatalf("expected %v, got %v", want, got)
	}
	// Error case: size mismatch
	_, err = EuclideanDistance(Float64Data{1}, Float64Data{1, 2})
	if !errors.Is(err, SizeErr) {
		t.Fatalf("expected SizeErr, got %v", err)
	}
}

func TestManhattanDistance_NormalAndError(t *testing.T) {
	x := Float64Data{1, -2, 3}
	y := Float64Data{4, -5, 0}
	got, err := ManhattanDistance(x, y)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if got != 9 {
		t.Fatalf("expected Manhattan distance 9, got %v", got)
	}
	// Error case: empty input
	_, err = ManhattanDistance(Float64Data{}, Float64Data{1})
	if !errors.Is(err, EmptyInputErr) {
		t.Fatalf("expected EmptyInputErr, got %v", err)
	}
}
