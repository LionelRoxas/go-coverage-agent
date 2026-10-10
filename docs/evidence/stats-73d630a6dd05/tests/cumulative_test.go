package stats

import (
	"errors"
	"math"
	"testing"
)

func cumulativeSlicesApproxEqual(t *testing.T, got, want []float64) {
	if len(got) != len(want) {
		t.Fatalf("slice length mismatch: got %d, want %d", len(got), len(want))
	}
	for i := range got {
		g, w := got[i], want[i]
		if math.IsNaN(g) && math.IsNaN(w) {
			continue
		}
		if math.IsInf(g, 0) || math.IsInf(w, 0) {
			if g != w {
				t.Fatalf("slice element %d mismatch: got %v, want %v", i, g, w)
			}
			continue
		}
		if math.Abs(g-w) > 1e-9 {
			t.Fatalf("slice element %d mismatch: got %v, want %v", i, g, w)
		}
	}
}

func TestCumulativeMax(t *testing.T) {
	cases := []struct {
		name    string
		input   Float64Data
		want    []float64
		wantErr error
	}{
		{"empty", Float64Data{}, nil, ErrEmptyInput},
		{"single", Float64Data{5}, []float64{5}, nil},
		{"mixed", Float64Data{3, 1, 4, 2, 5}, []float64{3, 3, 4, 4, 5}, nil},
		{"negative", Float64Data{-2, -5, -1, -3}, []float64{-2, -2, -1, -1}, nil},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := CumulativeMax(tc.input)
			if !errors.Is(err, tc.wantErr) {
				t.Fatalf("unexpected error: %v, want %v", err, tc.wantErr)
			}
			if err == nil {
				cumulativeSlicesApproxEqual(t, got, tc.want)
			}
		})
	}
}

func TestCumulativeMin(t *testing.T) {
	cases := []struct {
		name    string
		input   Float64Data
		want    []float64
		wantErr error
	}{
		{"empty", Float64Data{}, nil, ErrEmptyInput},
		{"single", Float64Data{7}, []float64{7}, nil},
		{"mixed", Float64Data{3, 1, 4, 2, 5}, []float64{3, 1, 1, 1, 1}, nil},
		{"negative", Float64Data{-2, -5, -1, -3}, []float64{-2, -5, -5, -5}, nil},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := CumulativeMin(tc.input)
			if !errors.Is(err, tc.wantErr) {
				t.Fatalf("unexpected error: %v, want %v", err, tc.wantErr)
			}
			if err == nil {
				cumulativeSlicesApproxEqual(t, got, tc.want)
			}
		})
	}
}

func TestCumulativeProduct(t *testing.T) {
	cases := []struct {
		name    string
		input   Float64Data
		want    []float64
		wantErr error
	}{
		{"empty", Float64Data{}, nil, ErrEmptyInput},
		{"single", Float64Data{4}, []float64{4}, nil},
		{"mixed", Float64Data{2, 3, 0, 5}, []float64{2, 6, 0, 0}, nil},
		{"negative", Float64Data{-1, 2, -3}, []float64{-1, -2, 6}, nil},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := CumulativeProduct(tc.input)
			if !errors.Is(err, tc.wantErr) {
				t.Fatalf("unexpected error: %v, want %v", err, tc.wantErr)
			}
			if err == nil {
				cumulativeSlicesApproxEqual(t, got, tc.want)
			}
		})
	}
}

func TestFloat64Data_CumulativeMax(t *testing.T) {
	cases := []struct {
		name    string
		input   Float64Data
		want    []float64
		wantErr error
	}{
		{"empty", Float64Data{}, nil, ErrEmptyInput},
		{"simple", Float64Data{1, 3, 2}, []float64{1, 3, 3}, nil},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := tc.input.CumulativeMax()
			if !errors.Is(err, tc.wantErr) {
				t.Fatalf("unexpected error: %v, want %v", err, tc.wantErr)
			}
			if err == nil {
				cumulativeSlicesApproxEqual(t, got, tc.want)
			}
		})
	}
}

func TestFloat64Data_CumulativeMin(t *testing.T) {
	cases := []struct {
		name    string
		input   Float64Data
		want    []float64
		wantErr error
	}{
		{"empty", Float64Data{}, nil, ErrEmptyInput},
		{"simple", Float64Data{5, 2, 4}, []float64{5, 2, 2}, nil},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := tc.input.CumulativeMin()
			if !errors.Is(err, tc.wantErr) {
				t.Fatalf("unexpected error: %v, want %v", err, tc.wantErr)
			}
			if err == nil {
				cumulativeSlicesApproxEqual(t, got, tc.want)
			}
		})
	}
}

func TestFloat64Data_CumulativeProduct(t *testing.T) {
	cases := []struct {
		name    string
		data    Float64Data
		want    []float64
		wantErr error
	}{
		{"empty", Float64Data{}, nil, ErrEmptyInput},
		{"single", Float64Data{5}, []float64{5}, nil},
		{"multiple", Float64Data{2, 3, 4}, []float64{2, 6, 24}, nil},
		{"zero", Float64Data{2, 0, 5}, []float64{2, 0, 0}, nil},
		{"negative", Float64Data{-2, 3}, []float64{-2, -6}, nil},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := tc.data.CumulativeProduct()
			if tc.wantErr != nil {
				if err == nil {
					t.Fatalf("expected error %v, got nil", tc.wantErr)
				}
				if !errors.Is(err, tc.wantErr) {
					t.Fatalf("expected error %v, got %v", tc.wantErr, err)
				}
				return
			}
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			cumulativeSlicesApproxEqual(t, got, tc.want)
		})
	}
}
