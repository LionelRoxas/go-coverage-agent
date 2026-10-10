package stats

import (
	"errors"
	"math"
	"testing"
)

func TestProduct(t *testing.T) {
	cases := []struct {
		name    string
		input   Float64Data
		want    float64
		wantErr error
		wantInf bool
		wantNaN bool
	}{
		{"empty", Float64Data{}, math.NaN(), ErrEmptyInput, false, true},
		{"normal", Float64Data{2, 3, 4}, 24, nil, false, false},
		{"overflow", Float64Data{math.MaxFloat64, 2}, math.Inf(1), nil, true, false},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := Product(tc.input)
			if !errors.Is(err, tc.wantErr) {
				t.Fatalf("expected error %v, got %v", tc.wantErr, err)
			}
			if tc.wantNaN {
				if !math.IsNaN(got) {
					t.Fatalf("expected NaN, got %v", got)
				}
				return
			}
			if tc.wantInf {
				if !math.IsInf(got, 1) {
					t.Fatalf("expected +Inf, got %v", got)
				}
				return
			}
			if diff := math.Abs(got - tc.want); diff > 1e-12 {
				t.Fatalf("expected %v, got %v", tc.want, got)
			}
		})
	}
}

func TestFloat64Data_Product(t *testing.T) {
	cases := []struct {
		name    string
		input   Float64Data
		want    float64
		wantErr error
		wantInf bool
		wantNaN bool
	}{
		{"empty", Float64Data{}, math.NaN(), ErrEmptyInput, false, true},
		{"normal", Float64Data{5, 0.5}, 2.5, nil, false, false},
		{"overflow", Float64Data{math.MaxFloat64, 2}, math.Inf(1), nil, true, false},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := tc.input.Product()
			if !errors.Is(err, tc.wantErr) {
				t.Fatalf("expected error %v, got %v", tc.wantErr, err)
			}
			if tc.wantNaN {
				if !math.IsNaN(got) {
					t.Fatalf("expected NaN, got %v", got)
				}
				return
			}
			if tc.wantInf {
				if !math.IsInf(got, 1) {
					t.Fatalf("expected +Inf, got %v", got)
				}
				return
			}
			if diff := math.Abs(got - tc.want); diff > 1e-12 {
				t.Fatalf("expected %v, got %v", tc.want, got)
			}
		})
	}
}
