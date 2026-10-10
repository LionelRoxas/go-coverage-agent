package stats

import (
	"errors"
	"math"
	"testing"
)

func TestProduct_EmptyInput(t *testing.T) {
	var empty Float64Data
	got, err := Product(empty)
	if !errors.Is(err, ErrEmptyInput) {
		t.Fatalf("expected ErrEmptyInput, got %v", err)
	}
	if !math.IsNaN(got) {
		t.Fatalf("expected NaN result for empty input, got %v", got)
	}
}

func TestProduct_NonEmpty(t *testing.T) {
	cases := []struct {
		name    string
		input   Float64Data
		want    float64
		wantInf bool
	}{
		{"simple", Float64Data{2, 3, 4}, 24, false},
		{"single", Float64Data{5}, 5, false},
		{"overflow", Float64Data{math.MaxFloat64, 2}, math.Inf(1), true},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := Product(tc.input)
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			if tc.wantInf {
				if !math.IsInf(got, 1) {
					t.Fatalf("expected +Inf, got %v", got)
				}
			} else {
				if math.Abs(got-tc.want) > 1e-12 {
					t.Fatalf("expected %v, got %v", tc.want, got)
				}
			}
		})
	}
}

func TestFloat64Data_Product(t *testing.T) {
	cases := []struct {
		name    string
		input   Float64Data
		want    float64
		wantInf bool
		wantErr bool
	}{
		{"empty", Float64Data{}, math.NaN(), false, true},
		{"simple", Float64Data{2, 3, 4}, 24, false, false},
		{"overflow", Float64Data{math.MaxFloat64, 2}, math.Inf(1), true, false},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := tc.input.Product()
			if tc.wantErr {
				if !errors.Is(err, ErrEmptyInput) {
					t.Fatalf("expected ErrEmptyInput, got %v", err)
				}
				if !math.IsNaN(got) {
					t.Fatalf("expected NaN result for empty input, got %v", got)
				}
				return
			}
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			if tc.wantInf {
				if !math.IsInf(got, 1) {
					t.Fatalf("expected +Inf, got %v", got)
				}
			} else {
				if math.Abs(got-tc.want) > 1e-12 {
					t.Fatalf("expected %v, got %v", tc.want, got)
				}
			}
		})
	}
}
