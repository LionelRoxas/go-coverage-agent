package stats

import (
	"errors"
	"math"
	"testing"
)

func TestRankData(t *testing.T) {
	cases := []struct {
		name string
		data Float64Data
		want Float64Data
	}{
		{"empty", Float64Data{}, Float64Data{}},
		{"no ties", Float64Data{10, 20, 30}, Float64Data{1, 2, 3}},
		{"with ties", Float64Data{5, 1, 5, 3}, Float64Data{3.5, 1, 3.5, 2}},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got := rankData(tc.data)
			if len(got) != len(tc.want) {
				t.Fatalf("len got %d want %d", len(got), len(tc.want))
			}
			for i := range got {
				if math.Abs(got[i]-tc.want[i]) > 1e-9 {
					t.Fatalf("index %d got %v want %v", i, got[i], tc.want[i])
				}
			}
		})
	}
}

func TestAutoCorrelation_Errors(t *testing.T) {
	// Empty input
	if _, err := AutoCorrelation(Float64Data{}, 0); !errors.Is(err, EmptyInputErr) {
		t.Fatalf("expected EmptyInputErr, got %v", err)
	}
	// Bounds error (negative lag)
	if _, err := AutoCorrelation(Float64Data{1, 2, 3}, -1); !errors.Is(err, BoundsErr) {
		t.Fatalf("expected BoundsErr for negative lag, got %v", err)
	}
	// Bounds error (lag >= len)
	if _, err := AutoCorrelation(Float64Data{1, 2, 3}, 3); !errors.Is(err, BoundsErr) {
		t.Fatalf("expected BoundsErr for lag >= len, got %v", err)
	}
	// Zero variance case
	if got, err := AutoCorrelation(Float64Data{5, 5, 5}, 1); err != nil || got != 0 {
		t.Fatalf("expected 0 with nil error for zero variance, got %v, err %v", got, err)
	}
}

func TestAutoCorrelation_Normal(t *testing.T) {
	data := Float64Data{1, 2, 3, 4}
	got, err := AutoCorrelation(data, 1)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	want := 0.25
	if math.Abs(got-want) > 1e-9 {
		t.Fatalf("got %v want %v", got, want)
	}
}

func TestCorrelation_Errors(t *testing.T) {
	// Empty input
	if _, err := Correlation(Float64Data{}, Float64Data{1}); !errors.Is(err, EmptyInputErr) {
		t.Fatalf("expected EmptyInputErr for empty data1, got %v", err)
	}
	// Size mismatch
	if _, err := Correlation(Float64Data{1, 2}, Float64Data{1}); !errors.Is(err, SizeErr) {
		t.Fatalf("expected SizeErr for size mismatch, got %v", err)
	}
	// Zero standard deviation (constant data)
	if got, err := Correlation(Float64Data{5, 5, 5}, Float64Data{1, 2, 3}); err != nil || got != 0 {
		t.Fatalf("expected 0 with nil error for zero std dev, got %v, err %v", got, err)
	}
}

func TestCorrelation_Normal(t *testing.T) {
	d1 := Float64Data{1, 2, 3}
	d2 := Float64Data{2, 4, 6}
	got, err := Correlation(d1, d2)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if math.Abs(got-1) > 1e-9 {
		t.Fatalf("expected correlation 1, got %v", got)
	}
	d3 := Float64Data{6, 4, 2}
	gotNeg, err := Correlation(d1, d3)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if math.Abs(gotNeg+1) > 1e-9 {
		t.Fatalf("expected correlation -1, got %v", gotNeg)
	}
}

func TestSpearman_Ties(t *testing.T) {
	d1 := Float64Data{1, 2, 2, 3}
	d2 := Float64Data{4, 1, 1, 2}
	// Expected correlation of ranks
	ranks1 := rankData(d1)
	ranks2 := rankData(d2)
	exp, err := Correlation(ranks1, ranks2)
	if err != nil {
		t.Fatalf("unexpected error computing expected correlation: %v", err)
	}
	got, err := Spearman(d1, d2)
	if err != nil {
		t.Fatalf("unexpected error from Spearman: %v", err)
	}
	if math.Abs(got-exp) > 1e-9 {
		t.Fatalf("Spearman %v differs from expected %v", got, exp)
	}
}

func TestPearson_Forward(t *testing.T) {
	d1 := Float64Data{1, 2, 3, 4}
	d2 := Float64Data{2, 3, 5, 7}
	corr, err1 := Correlation(d1, d2)
	if err1 != nil {
		t.Fatalf("Correlation error: %v", err1)
	}
	pear, err2 := Pearson(d1, d2)
	if err2 != nil {
		t.Fatalf("Pearson error: %v", err2)
	}
	if math.Abs(corr-pear) > 1e-9 {
		t.Fatalf("Pearson %v differs from Correlation %v", pear, corr)
	}
}
