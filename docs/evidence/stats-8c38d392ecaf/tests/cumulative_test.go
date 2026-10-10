package stats

import (
	"errors"
	"reflect"
	"testing"
)

func cumulativeSlicesEqual(a, b []float64) bool {
	return reflect.DeepEqual(a, b)
}

func TestCumulativeMax(t *testing.T) {
	cases := []struct {
		name    string
		input   Float64Data
		want    []float64
		wantErr error
	}{
		{"empty", Float64Data{}, nil, ErrEmptyInput},
		{"single", Float64Data{-2.5}, []float64{-2.5}, nil},
		{"normal", Float64Data{1, 3, 2, 5, 4}, []float64{1, 3, 3, 5, 5}, nil},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := CumulativeMax(tc.input)
			if !errors.Is(err, tc.wantErr) {
				t.Fatalf("expected error %v, got %v", tc.wantErr, err)
			}
			if err == nil && !cumulativeSlicesEqual(got, tc.want) {
				t.Fatalf("expected %v, got %v", tc.want, got)
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
		{"single", Float64Data{7.1}, []float64{7.1}, nil},
		{"normal", Float64Data{5, 2, 8, 1, 4}, []float64{5, 2, 2, 1, 1}, nil},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := CumulativeMin(tc.input)
			if !errors.Is(err, tc.wantErr) {
				t.Fatalf("expected error %v, got %v", tc.wantErr, err)
			}
			if err == nil && !cumulativeSlicesEqual(got, tc.want) {
				t.Fatalf("expected %v, got %v", tc.want, got)
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
		{"single", Float64Data{3}, []float64{3}, nil},
		{"normal", Float64Data{2, 3, 4}, []float64{2, 6, 24}, nil},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := CumulativeProduct(tc.input)
			if !errors.Is(err, tc.wantErr) {
				t.Fatalf("expected error %v, got %v", tc.wantErr, err)
			}
			if err == nil && !cumulativeSlicesEqual(got, tc.want) {
				t.Fatalf("expected %v, got %v", tc.want, got)
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
		{"normal", Float64Data{0, -1, 5, 3}, []float64{0, 0, 5, 5}, nil},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := tc.input.CumulativeMax()
			if !errors.Is(err, tc.wantErr) {
				t.Fatalf("expected error %v, got %v", tc.wantErr, err)
			}
			if err == nil && !cumulativeSlicesEqual(got, tc.want) {
				t.Fatalf("expected %v, got %v", tc.want, got)
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
		{"normal", Float64Data{4, 2, 6, 1}, []float64{4, 2, 2, 1}, nil},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := tc.input.CumulativeMin()
			if !errors.Is(err, tc.wantErr) {
				t.Fatalf("expected error %v, got %v", tc.wantErr, err)
			}
			if err == nil && !cumulativeSlicesEqual(got, tc.want) {
				t.Fatalf("expected %v, got %v", tc.want, got)
			}
		})
	}
}
