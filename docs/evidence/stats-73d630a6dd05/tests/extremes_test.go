package stats

import (
	"errors"
	"math"
	"testing"
)

func extremesEqualFloat64(a, b float64) bool {
	const eps = 1e-9
	if math.IsNaN(a) && math.IsNaN(b) {
		return true
	}
	if math.IsInf(a, 0) || math.IsInf(b, 0) {
		return a == b
	}
	return math.Abs(a-b) <= eps
}

func TestArgMax(t *testing.T) {
	cases := []struct {
		name    string
		input   []float64
		wantIdx int
		wantErr bool
	}{
		{"empty", []float64{}, -1, true},
		{"single", []float64{42}, 0, false},
		{"distinct", []float64{1, 3, 2, 5, 4}, 3, false},
		{"tie", []float64{7, 2, 7, 5}, 0, false},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			idx, err := ArgMax(Float64Data(tc.input))
			if tc.wantErr {
				if err == nil {
					t.Fatalf("expected error, got nil")
				}
				if !errors.Is(err, ErrEmptyInput) {
					t.Fatalf("expected ErrEmptyInput, got %v", err)
				}
				if idx != -1 {
					t.Fatalf("expected index -1 on error, got %d", idx)
				}
				return
			}
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			if idx != tc.wantIdx {
				t.Fatalf("expected index %d, got %d", tc.wantIdx, idx)
			}
		})
	}
}

func TestFloat64Data_ArgMax(t *testing.T) {
	// Reuse cases from TestArgMax but call the method
	cases := []struct {
		name    string
		input   []float64
		wantIdx int
		wantErr bool
	}{
		{"empty", []float64{}, -1, true},
		{"multiple", []float64{2, 9, 4, 9, 1}, 1, false},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			idx, err := Float64Data(tc.input).ArgMax()
			if tc.wantErr {
				if err == nil {
					t.Fatalf("expected error, got nil")
				}
				if !errors.Is(err, ErrEmptyInput) {
					t.Fatalf("expected ErrEmptyInput, got %v", err)
				}
				if idx != -1 {
					t.Fatalf("expected index -1 on error, got %d", idx)
				}
				return
			}
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			if idx != tc.wantIdx {
				t.Fatalf("expected index %d, got %d", tc.wantIdx, idx)
			}
		})
	}
}

func TestFloat64Data_ArgMin(t *testing.T) {
	cases := []struct {
		name    string
		input   []float64
		wantIdx int
		wantErr bool
	}{
		{"empty", []float64{}, -1, true},
		{"multiple", []float64{5, -2, 3, -2, 7}, 1, false},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			idx, err := Float64Data(tc.input).ArgMin()
			if tc.wantErr {
				if err == nil {
					t.Fatalf("expected error, got nil")
				}
				if !errors.Is(err, ErrEmptyInput) {
					t.Fatalf("expected ErrEmptyInput, got %v", err)
				}
				if idx != -1 {
					t.Fatalf("expected index -1 on error, got %d", idx)
				}
				return
			}
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			if idx != tc.wantIdx {
				t.Fatalf("expected index %d, got %d", tc.wantIdx, idx)
			}
		})
	}
}

func TestFloat64Data_Range(t *testing.T) {
	cases := []struct {
		name    string
		input   []float64
		want    float64
		wantErr bool
	}{
		{"empty", []float64{}, 0, true},
		{"single", []float64{3.14}, 0, false},
		{"multiple", []float64{1, 5, -2, 8, 4}, 10, false}, // max 8, min -2 => 10
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := Float64Data(tc.input).Range()
			if tc.wantErr {
				if err == nil {
					t.Fatalf("expected error, got nil")
				}
				if !errors.Is(err, ErrEmptyInput) {
					t.Fatalf("expected ErrEmptyInput, got %v", err)
				}
				return
			}
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			if !extremesEqualFloat64(got, tc.want) {
				t.Fatalf("expected range %v, got %v", tc.want, got)
			}
		})
	}
}
