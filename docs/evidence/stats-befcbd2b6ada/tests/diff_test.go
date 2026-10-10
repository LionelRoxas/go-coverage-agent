package stats

import (
	"errors"
	"math"
	"testing"
)

func diffSlicesEqual(a, b []float64) bool {
	if len(a) != len(b) {
		return false
	}
	const eps = 1e-12
	for i := range a {
		av, bv := a[i], b[i]
		if math.IsNaN(av) && math.IsNaN(bv) {
			continue
		}
		if math.IsInf(av, 0) && math.IsInf(bv, 0) && (math.Signbit(av) == math.Signbit(bv)) {
			continue
		}
		if math.Abs(av-bv) > eps {
			return false
		}
	}
	return true
}

func TestDiff(t *testing.T) {
	cases := []struct {
		name    string
		input   Float64Data
		want    []float64
		wantErr error
	}{
		{"empty", Float64Data{}, nil, ErrEmptyInput},
		{"single", Float64Data{42}, []float64{}, nil},
		{"multiple", Float64Data{1, 3, 2, 5}, []float64{2, -1, 3}, nil},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := Diff(tc.input)
			if !errors.Is(err, tc.wantErr) {
				t.Fatalf("expected error %v, got %v", tc.wantErr, err)
			}
			if err == nil && !diffSlicesEqual(got, tc.want) {
				t.Fatalf("expected %v, got %v", tc.want, got)
			}
		})
	}
}

func TestFloat64Data_Diff(t *testing.T) {
	input := Float64Data{10, 15, 12}
	want := []float64{5, -3}
	got, err := input.Diff()
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if !diffSlicesEqual(got, want) {
		t.Fatalf("expected %v, got %v", want, got)
	}
}

func TestPercentChange(t *testing.T) {
	cases := []struct {
		name    string
		input   Float64Data
		want    []float64
		wantErr error
	}{
		{"empty", Float64Data{}, nil, ErrEmptyInput},
		{"single", Float64Data{5}, []float64{}, nil},
		{"normal", Float64Data{100, 150, 120}, []float64{0.5, -0.2}, nil},
		{"zeroDenom", Float64Data{0, 0, 2}, []float64{math.NaN(), math.Inf(1)}, nil},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := PercentChange(tc.input)
			if !errors.Is(err, tc.wantErr) {
				t.Fatalf("expected error %v, got %v", tc.wantErr, err)
			}
			if err == nil && !diffSlicesEqual(got, tc.want) {
				t.Fatalf("expected %v, got %v", tc.want, got)
			}
		})
	}
}

func TestFloat64Data_PercentChange(t *testing.T) {
	input := Float64Data{0, 0, 2}
	want := []float64{math.NaN(), math.Inf(1)}
	got, err := input.PercentChange()
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if !diffSlicesEqual(got, want) {
		t.Fatalf("expected %v, got %v", want, got)
	}
}
