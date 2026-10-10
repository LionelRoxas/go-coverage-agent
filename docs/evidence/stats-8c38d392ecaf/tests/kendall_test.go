package stats

import (
	"errors"
	"math"
	"testing"
)

func TestKendallTau_Errors(t *testing.T) {
	cases := []struct {
		name    string
		d1, d2  Float64Data
		wantErr error
	}{
		{"EmptyInput", Float64Data{}, Float64Data{1, 2}, ErrEmptyInput},
		{"SizeMismatch", Float64Data{1, 2, 3}, Float64Data{1, 2}, ErrSize},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := KendallTau(tc.d1, tc.d2)
			if !errors.Is(err, tc.wantErr) {
				t.Fatalf("expected error %v, got %v", tc.wantErr, err)
			}
			if !math.IsNaN(got) {
				t.Fatalf("expected result NaN, got %v", got)
			}
		})
	}
}

func TestKendallTau_Normal(t *testing.T) {
	cases := []struct {
		name        string
		d1, d2      Float64Data
		want        float64
		wantDenZero bool
	}{
		{"SingleElement", Float64Data{5}, Float64Data{10}, 0, true},
		{"PerfectCorrelation", Float64Data{1, 2, 3}, Float64Data{1, 2, 3}, 1, false},
		{"TiesCase", Float64Data{1, 1, 2}, Float64Data{1, 2, 2}, 0.5, false},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := KendallTau(tc.d1, tc.d2)
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			if tc.wantDenZero {
				if got != 0 {
					t.Fatalf("expected 0 result for denominator zero, got %v", got)
				}
				return
			}
			if math.Abs(got-tc.want) > 1e-9 {
				t.Fatalf("expected %v, got %v", tc.want, got)
			}
		})
	}
}

func TestFloat64Data_KendallTau(t *testing.T) {
	d1 := Float64Data{1, 2, 3}
	d2 := Float64Data{3, 2, 1}
	want, err := KendallTau(d1, d2)
	if err != nil {
		t.Fatalf("unexpected error from function: %v", err)
	}
	got, err := d1.KendallTau(d2)
	if err != nil {
		t.Fatalf("unexpected error from method: %v", err)
	}
	if math.Abs(got-want) > 1e-9 {
		t.Fatalf("method result %v differs from function result %v", got, want)
	}
}
