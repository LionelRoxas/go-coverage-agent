package stats

import (
	"errors"
	"math"
	"testing"
)

func quartileApproxEqual(a, b float64) bool {
	const eps = 1e-9
	if math.IsNaN(a) && math.IsNaN(b) {
		return true
	}
	return math.Abs(a-b) <= eps
}

func TestQuartile(t *testing.T) {
	cases := []struct {
		name  string
		input Float64Data
		want  Quartiles
		err   error
	}{
		{"empty", Float64Data{}, Quartiles{}, EmptyInputErr},
		{"single", Float64Data{42}, Quartiles{}, EmptyInputErr},
		{"even", Float64Data{1, 2, 3, 4}, Quartiles{1.5, 2.5, 3.5}, nil},
		{"odd", Float64Data{7, 1, 5, 3, 9}, Quartiles{2, 5, 8}, nil},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := Quartile(tc.input)
			if tc.err != nil {
				if !errors.Is(err, tc.err) {
					t.Fatalf("expected error %v, got %v", tc.err, err)
				}
				return
			}
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			if !quartileApproxEqual(got.Q1, tc.want.Q1) ||
				!quartileApproxEqual(got.Q2, tc.want.Q2) ||
				!quartileApproxEqual(got.Q3, tc.want.Q3) {
				t.Fatalf("got %v, want %v", got, tc.want)
			}
		})
	}
}

func TestInterQuartileRange(t *testing.T) {
	cases := []struct {
		name  string
		input Float64Data
		want  float64
		err   error
	}{
		{"empty", Float64Data{}, math.NaN(), EmptyInputErr},
		{"single", Float64Data{5}, math.NaN(), EmptyInputErr},
		{"even", Float64Data{1, 2, 3, 4}, 2.0, nil},
		{"odd", Float64Data{7, 1, 5, 3, 9}, 6.0, nil},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := InterQuartileRange(tc.input)
			if tc.err != nil {
				if !errors.Is(err, tc.err) {
					t.Fatalf("expected error %v, got %v", tc.err, err)
				}
				if !math.IsNaN(got) {
					t.Fatalf("expected NaN result, got %v", got)
				}
				return
			}
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			if !quartileApproxEqual(got, tc.want) {
				t.Fatalf("got %v, want %v", got, tc.want)
			}
		})
	}
}

func TestMidhinge(t *testing.T) {
	cases := []struct {
		name  string
		input Float64Data
		want  float64
		err   error
	}{
		{"empty", Float64Data{}, math.NaN(), EmptyInputErr},
		{"single", Float64Data{5}, math.NaN(), EmptyInputErr},
		{"even", Float64Data{1, 2, 3, 4}, 2.5, nil},
		{"odd", Float64Data{7, 1, 5, 3, 9}, 5.0, nil},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := Midhinge(tc.input)
			if tc.err != nil {
				if !errors.Is(err, tc.err) {
					t.Fatalf("expected error %v, got %v", tc.err, err)
				}
				if !math.IsNaN(got) {
					t.Fatalf("expected NaN result, got %v", got)
				}
				return
			}
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			if !quartileApproxEqual(got, tc.want) {
				t.Fatalf("got %v, want %v", got, tc.want)
			}
		})
	}
}

func TestTrimean(t *testing.T) {
	cases := []struct {
		name  string
		input Float64Data
		want  float64
		err   error
	}{
		{"empty", Float64Data{}, math.NaN(), EmptyInputErr},
		{"single", Float64Data{5}, math.NaN(), EmptyInputErr},
		{"even", Float64Data{1, 2, 3, 4}, 2.5, nil},
		{"odd", Float64Data{7, 1, 5, 3, 9}, 5.0, nil},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := Trimean(tc.input)
			if tc.err != nil {
				if !errors.Is(err, tc.err) {
					t.Fatalf("expected error %v, got %v", tc.err, err)
				}
				if !math.IsNaN(got) {
					t.Fatalf("expected NaN result, got %v", got)
				}
				return
			}
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			if !quartileApproxEqual(got, tc.want) {
				t.Fatalf("got %v, want %v", got, tc.want)
			}
		})
	}
}
