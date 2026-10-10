package stats

import (
	"errors"
	"math"
	"testing"
)

func cumulativeApproxEqual(t *testing.T, got, want []float64) {
	if len(got) != len(want) {
		t.Fatalf("length mismatch: got %d, want %d", len(got), len(want))
	}
	const eps = 1e-9
	for i := range got {
		if math.Abs(got[i]-want[i]) > eps {
			t.Fatalf("at index %d: got %v, want %v", i, got[i], want[i])
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
		{"single", Float64Data{-2}, []float64{-2}, nil},
		{"mixed", Float64Data{1, 3, 2, 5, 4}, []float64{1, 3, 3, 5, 5}, nil},
		{"decreasing", Float64Data{5, 4, 3}, []float64{5, 5, 5}, nil},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := CumulativeMax(tc.input)
			if tc.wantErr != nil {
				if err == nil || !errors.Is(err, tc.wantErr) {
					t.Fatalf("expected error %v, got %v", tc.wantErr, err)
				}
				return
			}
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			cumulativeApproxEqual(t, got, tc.want)
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
		{"mixed", Float64Data{5, 2, 8, 1, 4}, []float64{5, 2, 2, 1, 1}, nil},
		{"increasing", Float64Data{1, 2, 3}, []float64{1, 1, 1}, nil},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := CumulativeMin(tc.input)
			if tc.wantErr != nil {
				if err == nil || !errors.Is(err, tc.wantErr) {
					t.Fatalf("expected error %v, got %v", tc.wantErr, err)
				}
				return
			}
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			cumulativeApproxEqual(t, got, tc.want)
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
		{"single", Float64Data{3}, []float64{3}, nil},
		{"positive", Float64Data{2, 3, 4}, []float64{2, 6, 24}, nil},
		{"zero", Float64Data{5, 0, 2}, []float64{5, 0, 0}, nil},
		{"negative", Float64Data{-1, 2, -3}, []float64{-1, -2, 6}, nil},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := CumulativeProduct(tc.input)
			if tc.wantErr != nil {
				if err == nil || !errors.Is(err, tc.wantErr) {
					t.Fatalf("expected error %v, got %v", tc.wantErr, err)
				}
				return
			}
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			cumulativeApproxEqual(t, got, tc.want)
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
		{"mixed", Float64Data{2, 1, 4}, []float64{2, 2, 4}, nil},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := tc.input.CumulativeMax()
			if tc.wantErr != nil {
				if err == nil || !errors.Is(err, tc.wantErr) {
					t.Fatalf("expected error %v, got %v", tc.wantErr, err)
				}
				return
			}
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			cumulativeApproxEqual(t, got, tc.want)
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
		{"mixed", Float64Data{3, 5, 2, 6}, []float64{3, 3, 2, 2}, nil},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := tc.input.CumulativeMin()
			if tc.wantErr != nil {
				if err == nil || !errors.Is(err, tc.wantErr) {
					t.Fatalf("expected error %v, got %v", tc.wantErr, err)
				}
				return
			}
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			cumulativeApproxEqual(t, got, tc.want)
		})
	}
}

func TestFloat64Data_CumulativeProduct(t *testing.T) {
	cases := []struct {
		name    string
		input   Float64Data
		want    []float64
		wantErr bool
	}{
		{"empty slice", Float64Data{}, nil, true},
		{"single element", Float64Data{5}, []float64{5}, false},
		{"multiple positives", Float64Data{2, 3, 4}, []float64{2, 6, 24}, false},
		{"contains zero", Float64Data{2, 0, 5}, []float64{2, 0, 0}, false},
		{"negative numbers", Float64Data{-2, 3}, []float64{-2, -6}, false},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := tc.input.CumulativeProduct()
			if tc.wantErr {
				if err == nil {
					t.Fatalf("expected error, got nil")
				}
				return
			}
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			cumulativeApproxEqual(t, got, tc.want)
		})
	}
}
