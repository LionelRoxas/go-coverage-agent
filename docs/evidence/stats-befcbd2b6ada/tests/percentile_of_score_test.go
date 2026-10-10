package stats

import (
	"errors"
	"math"
	"testing"
)

func percentileOfScoreAssertEqual(t *testing.T, got, want float64) {
	const eps = 1e-9
	if math.IsNaN(want) {
		if !math.IsNaN(got) {
			t.Errorf("expected NaN, got %v", got)
		}
		return
	}
	if math.Abs(got-want) > eps {
		t.Errorf("expected %v, got %v", want, got)
	}
}

func TestPercentileOfScore_EmptyInput(t *testing.T) {
	var empty Float64Data
	got, err := PercentileOfScore(empty, 1.0)
	if !errors.Is(err, ErrEmptyInput) {
		t.Errorf("expected ErrEmptyInput, got %v", err)
	}
	percentileOfScoreAssertEqual(t, got, math.NaN())
}

func TestPercentileOfScore_Basic(t *testing.T) {
	type testCase struct {
		name  string
		data  []float64
		score float64
		want  float64
	}
	cases := []testCase{{
		name:  "score less than all",
		data:  []float64{1, 2, 3, 4, 5},
		score: 0,
		want:  0,
	}, {
		name:  "score greater than all",
		data:  []float64{1, 2, 3, 4, 5},
		score: 6,
		want:  100,
	}, {
		name:  "score equal to middle value",
		data:  []float64{1, 2, 3, 4, 5},
		score: 3,
		want:  50,
	}, {
		name:  "score between values",
		data:  []float64{1, 2, 3, 4, 5},
		score: 2.5,
		want:  40,
	}, {
		name:  "duplicate values with equal score",
		data:  []float64{1, 2, 2, 2, 3},
		score: 2,
		want:  50,
	}}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := PercentileOfScore(tc.data, tc.score)
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			percentileOfScoreAssertEqual(t, got, tc.want)
		})
	}
}

func TestFloat64Data_PercentileOfScore_Forward(t *testing.T) {
	data := Float64Data{1, 2, 3, 4, 5}
	got, err := data.PercentileOfScore(3)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	percentileOfScoreAssertEqual(t, got, 50)
}
