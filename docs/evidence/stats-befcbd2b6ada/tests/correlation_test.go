package stats

import (
	"errors"
	"math"
	"testing"
)

func correlationApproxEqual(t *testing.T, got, want float64) {
	const eps = 1e-9
	if math.IsNaN(got) && math.IsNaN(want) {
		return
	}
	if math.IsInf(got, 0) || math.IsInf(want, 0) {
		if got != want {
			t.Fatalf("got %v, want %v", got, want)
		}
		return
	}
	if math.Abs(got-want) > eps {
		t.Fatalf("got %v, want %v (diff %v > %v)", got, want, math.Abs(got-want), eps)
	}
}

func TestRankData(t *testing.T) {
	cases := []struct {
		name string
		data Float64Data
		want Float64Data
	}{
		{"empty", Float64Data{}, Float64Data{}},
		{"no ties", Float64Data{10, 20, 30}, Float64Data{1, 2, 3}},
		{"with ties", Float64Data{10, 20, 20, 30}, Float64Data{1, 2.5, 2.5, 4}},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got := rankData(tc.data)
			if len(got) != len(tc.want) {
				t.Fatalf("length mismatch: got %d, want %d", len(got), len(tc.want))
			}
			for i := range got {
				if math.Abs(got[i]-tc.want[i]) > 1e-9 {
					t.Fatalf("at index %d: got %v, want %v", i, got[i], tc.want[i])
				}
			}
		})
	}
}

func TestAutoCorrelation(t *testing.T) {
	cases := []struct {
		name    string
		data    Float64Data
		lag     int
		want    float64
		wantErr error
	}{
		{"empty input", Float64Data{}, 0, 0, EmptyInputErr},
		{"lag out of bounds negative", Float64Data{1, 2, 3}, -1, 0, BoundsErr},
		{"lag out of bounds too large", Float64Data{1, 2, 3}, 3, 0, BoundsErr},
		{"zero variance", Float64Data{5, 5, 5, 5}, 1, 0, nil},
		{"regular case", Float64Data{1, 2, 3, 4, 5}, 1, 0.4, nil},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := AutoCorrelation(tc.data, tc.lag)
			if !errors.Is(err, tc.wantErr) {
				t.Fatalf("unexpected error: got %v, want %v", err, tc.wantErr)
			}
			if tc.wantErr == nil {
				correlationApproxEqual(t, got, tc.want)
			}
		})
	}
}

func TestCorrelation(t *testing.T) {
	cases := []struct {
		name    string
		d1, d2  Float64Data
		want    float64
		wantErr error
	}{
		{"empty input", Float64Data{}, Float64Data{}, math.NaN(), EmptyInputErr},
		{"size mismatch", Float64Data{1, 2}, Float64Data{1, 2, 3}, math.NaN(), SizeErr},
		{"zero stddev", Float64Data{5, 5, 5}, Float64Data{1, 2, 3}, 0, nil},
		{"perfect positive", Float64Data{1, 2, 3}, Float64Data{1, 2, 3}, 1, nil},
		{"perfect negative", Float64Data{1, 2, 3}, Float64Data{3, 2, 1}, -1, nil},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := Correlation(tc.d1, tc.d2)
			if !errors.Is(err, tc.wantErr) {
				t.Fatalf("unexpected error: got %v, want %v", err, tc.wantErr)
			}
			if tc.wantErr == nil {
				if math.IsNaN(tc.want) {
					if !math.IsNaN(got) {
						t.Fatalf("expected NaN, got %v", got)
					}
				} else {
					correlationApproxEqual(t, got, tc.want)
				}
			}
		})
	}
}

func TestSpearman(t *testing.T) {
	cases := []struct {
		name    string
		d1, d2  Float64Data
		want    float64
		wantErr error
	}{
		{"empty input", Float64Data{}, Float64Data{}, math.NaN(), EmptyInputErr},
		{"size mismatch", Float64Data{1, 2}, Float64Data{1, 2, 3}, math.NaN(), SizeErr},
		{"tied values", Float64Data{1, 2, 2, 3}, Float64Data{4, 5, 5, 6}, 1, nil},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := Spearman(tc.d1, tc.d2)
			if !errors.Is(err, tc.wantErr) {
				t.Fatalf("unexpected error: got %v, want %v", err, tc.wantErr)
			}
			if tc.wantErr == nil {
				correlationApproxEqual(t, got, tc.want)
			}
		})
	}
}

func TestPearson(t *testing.T) {
	// Pearson simply forwards to Correlation; reuse a normal case
	d1 := Float64Data{1, 2, 3, 4}
	d2 := Float64Data{2, 4, 6, 8}
	want := 1.0 // perfectly linearly related
	got, err := Pearson(d1, d2)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	correlationApproxEqual(t, got, want)
}
